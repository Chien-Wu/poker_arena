"""A game is a capped sequence of hands with stacks carried between hands."""
from __future__ import annotations
from dataclasses import asdict
from .config import Config, Entry, GameConfig, ExecutionConfig
from .contracts import Action, ContractError, GameContext
from .engine import Hand
from .execution import BotFailure, BotTimeout, make_runner
from .registry import Registry
from utils.randomness import derive_seed
from utils.io import Journal


def play_game(entries: list[Entry], game_id: str, *, game: GameConfig,
              execution: ExecutionConfig, seed: int, registry: Registry,
              journal: Journal | None = None, purpose: str = "qualifier") -> dict:
    game.validate(); execution.validate()
    if not 2 <= len(entries) <= 9 or len({e.id for e in entries}) != len(entries):
        raise ContractError("Games require 2–9 distinct player ids")
    for e in entries: registry.check(e.bot, len(entries))
    runners = {}
    failures = {e.id: 0 for e in entries}
    disabled = set()
    stats = {e.id: {"decisions": 0, "failures": 0, "timeouts": 0, "upstream_calls": 0,
                    "adapter_repairs": 0} for e in entries}
    stacks = [game.initial_stack] * len(entries)
    ids = [e.id for e in entries]
    hand_count = 0
    button = 0
    journal = journal or Journal(None)

    def fault(player_id, exc, method):
        failures[player_id] += 1
        stats[player_id]["failures"] += 1
        if isinstance(exc, BotTimeout): stats[player_id]["timeouts"] += 1
        journal.write("faults", {"game_id": game_id, "player_id": player_id,
                                 "method": method, "error": str(exc)})
        if execution.failure_policy == "abort": raise exc
        # A timeout kills the process; do not attempt further protocol requests.
        if isinstance(exc, BotTimeout) or failures[player_id] >= execution.max_failures_per_game:
            disabled.add(player_id)
            runners[player_id].close()

    def notify(method, data, recipients=None):
        for player_id in (ids if recipients is None else recipients):
            if player_id in disabled: continue
            try: runners[player_id].call(method, data, execution.event_timeout_ms)
            except (BotFailure, ContractError) as exc: fault(player_id, exc, method)

    try:
        # Missing code/models and constructor errors are fatal, never disguised as integrations.
        for e in entries:
            runners[e.id] = make_runner(registry, e, derive_seed(seed, "policy", game_id, e.id), execution)
        for seat, e in enumerate(entries):
            context = GameContext(1, game_id, e.id, seat, tuple(ids), game.small_blind,
                                  game.big_blind, game.ante, game.initial_stack, game.hands_per_game)
            notify("on_game_start", context, [e.id])
        for hand_number in range(1, game.hands_per_game + 1):
            live = [i for i, stack in enumerate(stacks) if stack > 0]
            if len(live) < 2: break
            if button not in live:
                button = next((button + offset) % len(stacks) for offset in range(1, len(stacks)+1)
                              if (button + offset) % len(stacks) in live)
            sb, bb, ante = game.blinds(hand_number)
            hand = Hand(ids, stacks, button=button, small_blind=sb, big_blind=bb, ante=ante,
                        seed=derive_seed(seed, "deal", game_id, hand_number), game_id=game_id,
                        hand_number=hand_number, action_timeout_ms=execution.action_timeout_ms,
                        hands_remaining=game.hands_per_game - hand_number)
            for seat in live:
                notify("on_hand_start", hand.observation(seat), [ids[seat]])
            seen = 0
            def publish():
                nonlocal seen
                for event in hand.history[seen:]: notify("on_event", event)
                seen = len(hand.history)
            publish()
            while not hand.terminal:
                if len(hand.actions) >= game.max_actions_per_hand:
                    raise RuntimeError("max_actions_per_hand reached; hand aborted, not force-settled")
                seat = hand.actor
                player_id = ids[seat]
                obs = hand.observation(seat)
                fallback = False
                elapsed = 0.0
                if player_id in disabled:
                    action = Action("check" if "check" in obs.legal_actions.types else "fold")
                    fallback = True
                else:
                    try:
                        action = runners[player_id].call("act", obs, execution.action_timeout_ms)
                        if isinstance(action, dict): action = Action.from_dict(action)
                        if not isinstance(action, Action): raise ContractError("Bot returned a non-Action")
                        obs.legal_actions.validate(action)
                        elapsed = runners[player_id].last_elapsed_ms
                    except (BotFailure, ContractError, TypeError, ValueError) as exc:
                        fault(player_id, exc, "act")
                        action = Action("check" if "check" in obs.legal_actions.types else "fold")
                        fallback = True
                stats[player_id]["decisions"] += 1
                telemetry = runners[player_id].telemetry
                for key in ("upstream_calls", "adapter_repairs"):
                    value = telemetry.get(key, stats[player_id][key])
                    if type(value) is int and value >= 0: stats[player_id][key] = value
                journal.write("actions", {"game_id": game_id, "hand_id": hand.hand_id,
                                          "player_id": player_id, "street": hand.street,
                                          "legal": asdict(obs.legal_actions), "action": action.to_dict(),
                                          "fallback": fallback, "elapsed_ms": round(elapsed, 4),
                                          "telemetry": telemetry, "purpose": purpose})
                hand.apply(action)
                publish()
            result = hand.result()
            notify("on_hand_end", result)
            journal.write("private_hands", {"purpose": purpose, "record": hand.replay_record()})
            journal.write("public_hands", {"purpose": purpose, "game_id": game_id,
                                          "player_ids": ids, "result": asdict(result)})
            stacks = list(hand.stacks)
            hand_count += 1
            button = (button + 1) % len(stacks)
        result = {"game_id": game_id, "purpose": purpose, "seats": ids,
                  "hands": hand_count, "stacks": dict(zip(ids, stacks)),
                  "stats": stats, "disabled": sorted(disabled)}
        notify("on_game_end", result)
        journal.write("games", result)
        return result
    finally:
        for runner in runners.values(): runner.close()
