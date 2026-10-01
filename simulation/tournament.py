"""Rank-points tournament from the supplied screenshot, plus explicit gap rules."""
from __future__ import annotations
from dataclasses import asdict, replace
import itertools
import platform
import random
from pathlib import Path
from .config import Config
from .game import play_game
from .registry import Registry
from utils.io import Journal
from utils.randomness import derive_seed


def group_sizes(count: int, target: int) -> list[int]:
    if count < 2 or target < 2: raise ValueError("Need at least 2 players and group_size >= 2")
    groups = (count + target - 1) // target
    if count < 2 * groups:
        raise ValueError("Cannot partition into tables of 2 or more at this group size; add an entry")
    base, remainder = divmod(count, groups)
    return [base + (i < remainder) for i in range(groups)]


def partition(order: list[str], sizes: list[int]) -> list[list[str]]:
    if sum(sizes) != len(order): raise ValueError("Partition size mismatch")
    result, offset = [], 0
    for size in sizes:
        result.append(order[offset:offset+size]); offset += size
    return result


def tied_groups(values: dict[str, float]) -> list[list[str]]:
    by_value = {}
    for key, value in values.items(): by_value.setdefault(value, []).append(key)
    return [sorted(by_value[value]) for value in sorted(by_value, reverse=True)]


def placement_points(ranking: list[list[str]]) -> dict[str, float]:
    """For an unresolved tie, average the occupied ranks' points. Never pick a fake winner."""
    total = sum(map(len, ranking))
    result, consumed = {}, 0
    for group in ranking:
        points = sum(total - i for i in range(consumed, consumed + len(group))) / len(group)
        result.update((player, points) for player in group)
        consumed += len(group)
    return result


class Tournament:
    def __init__(self, config: Config, *, registry: Registry | None = None,
                 output: str | Path | None = None, progress=None, game_function=None):
        self.config = config.resolved()
        self.registry = registry or Registry()
        self.entries = {p.id: p for p in self.config.players}
        self.progress = progress or (lambda event: None)
        self.game_function = game_function or play_game
        self.sizes = group_sizes(len(self.entries), config.tournament.group_size)
        if config.tournament.require_equal_groups and len(set(self.sizes)) > 1:
            raise ValueError("Unequal groups forbidden by configuration")
        for entry in self.entries.values(): self.registry.check(entry.bot, max(self.sizes))
        self.journal = Journal(output)
        self.unresolved = []
        self.rounds = []
        self.games = []
        self.tie_counter = 0

    def _game(self, seats, game_id, purpose="qualifier"):
        game_cfg = self.config.game
        if purpose == "tiebreak":
            game_cfg = replace(game_cfg, hands_per_game=self.config.tournament.tiebreak_hands, blind_schedule=[])
        result = self.game_function([self.entries[x] for x in seats], game_id, game=game_cfg,
                                    execution=self.config.execution, seed=self.config.seed,
                                    registry=self.registry, journal=self.journal, purpose=purpose)
        self.games.append(result)
        self.progress({"type": "game_finished", "game": result})
        return result

    def _resolve_tie(self, players, context, attempt=0):
        if len(players) <= 1: return [players]
        if attempt >= self.config.tournament.tiebreak_attempts:
            record = {"context": context, "players": sorted(players), "attempts": attempt}
            self.unresolved.append(record)
            self.journal.write("unresolved_ties", record)
            if self.config.tournament.unresolved_ties == "error":
                raise RuntimeError(f"Unresolved tie after bounded heads-up playoffs: {players}")
            return [sorted(players)]
        # More than two tied bots: a heads-up round-robin, with two swapped-seat
        # legs per pair. A tied pair receives half a playoff win each.
        scores = dict.fromkeys(players, 0.0)
        pair_records = []
        for a, b in itertools.combinations(sorted(players), 2):
            self.tie_counter += 1
            net = 0
            for leg, seats in enumerate(([a, b], [b, a])):
                result = self._game(seats, f"tb{self.tie_counter}:leg{leg}", "tiebreak")
                net += result["stacks"][a] - result["stacks"][b]
            if net > 0: scores[a] += 1
            elif net < 0: scores[b] += 1
            else:
                scores[a] += 0.5; scores[b] += 0.5
            pair_records.append({"a": a, "b": b, "net_chip_difference_two_legs": net})
        self.journal.write("playoffs", {"context": context, "attempt": attempt + 1,
                                      "scores": scores, "pairs": pair_records})
        ranking = []
        for tied in tied_groups(scores):
            ranking.extend(self._resolve_tie(tied, context, attempt + 1) if len(tied) > 1 else [tied])
        return ranking

    def _rank(self, values, context, *, final=False):
        if self.config.tournament.tiebreak_scope == "final" and not final:
            ranking = tied_groups(values)
            if any(len(g)>1 for g in ranking):
                self.journal.write("shared_intermediate_ties", {"context":context,"ranking":ranking})
            return ranking
        result = []
        for group in tied_groups(values):
            result.extend(self._resolve_tie(group, context) if len(group) > 1 else [group])
        return result

    def run(self):
        cfg = self.config
        cumulative = dict.fromkeys(self.entries, 0.0)
        order = list(self.entries)
        random.Random(derive_seed(cfg.seed, "initial_groups")).shuffle(order)
        initial_order = list(order)
        self.journal.summary("config", cfg.to_dict())
        self.journal.summary("provenance", {"python": platform.python_version(),
                                          "engine_profile": "nlhe-moving-button-v1",
                                          "bot_fingerprints": {p.id: self.registry.fingerprint(p.bot) for p in cfg.players},
                                          "manifests": {p.bot: self.registry.manifest(p.bot) for p in cfg.players}})
        try:
            for round_number in range(1, cfg.tournament.rounds + 1):
                groups = partition(order if cfg.tournament.regroup else initial_order, self.sizes)
                group_records = []
                for gi, group in enumerate(groups):
                    game_points = dict.fromkeys(group, 0.0)
                    records = []
                    for cycle in range(cfg.tournament.rotation_cycles):
                        for rotation in range(len(group)):
                            seats = group[rotation:] + group[:rotation]
                            game_id = f"r{round_number}:g{gi}:c{cycle}:s{rotation}"
                            result = self._game(seats, game_id)
                            ranking = self._rank(result["stacks"], f"{game_id}:chip_rank")
                            points = placement_points(ranking)
                            for player, value in points.items(): game_points[player] += value
                            records.append({"game_id": game_id, "seats": seats, "stacks": result["stacks"],
                                            "ranking": ranking, "points": points})
                    rank = self._rank(game_points, f"r{round_number}:g{gi}:game_points")
                    round_points = placement_points(rank)
                    for player, value in round_points.items(): cumulative[player] += value
                    group_records.append({"players": group, "games": records, "game_points": game_points,
                                          "ranking": rank, "round_points": round_points})
                # Score ties are broken by HU before regrouping, but playoff wins
                # never change the cumulative point totals.
                current_rank = self._rank(cumulative, f"r{round_number}:cumulative", final=round_number == cfg.tournament.rounds)
                order = [p for group in current_rank for p in group]
                record = {"round": round_number, "groups": group_records,
                          "cumulative_points": dict(cumulative), "ranking": current_rank}
                self.rounds.append(record)
                self.journal.summary("checkpoint", {"completed_round": round_number, "rounds": self.rounds,
                                                     "cumulative_points": cumulative, "next_order": order})
                self.progress({"type": "round_finished", "round": record})
            # The last round's cumulative ranking already includes HU tie-breaks.
            final_rank = self.rounds[-1]["ranking"]
            leaderboard = []
            rank_number = 1
            for tied in final_rank:
                for player in tied:
                    stats = {key: 0 for key in ("decisions", "failures", "timeouts", "upstream_calls", "adapter_repairs")}
                    hands = net = 0
                    for game in self.games:
                        if game["purpose"] != "qualifier" or player not in game["stacks"]: continue
                        hands += game["hands"]
                        net += game["stacks"][player] - cfg.game.initial_stack
                        for key in stats: stats[key] += game.get("stats", {}).get(player, {}).get(key, 0)
                    leaderboard.append({"rank": rank_number, "player_id": player,
                                        "bot": self.entries[player].bot, "points": cumulative[player],
                                        "tied": len(tied) > 1, "qualifier_hands_at_table": hands,
                                        "qualifier_net_chips": net, **stats})
                rank_number += len(tied)
            summary = {"schema_version": 1, "status": "complete_with_unresolved_ties" if self.unresolved else "complete",
                       "seed": cfg.seed, "config": cfg.to_dict(), "group_sizes": self.sizes,
                       "warnings": (["Group sizes differ; screenshot-style points use each group's size."]
                                    if len(set(self.sizes)) > 1 else []),
                       "leaderboard": leaderboard, "ranking": final_rank,
                       "rounds": self.rounds, "qualifier_games": sum(g["purpose"] == "qualifier" for g in self.games),
                       "tiebreak_games": sum(g["purpose"] == "tiebreak" for g in self.games),
                       "total_hands": sum(g["hands"] for g in self.games), "unresolved_ties": self.unresolved}
            self.journal.summary("summary", summary)
            self.journal.csv("leaderboard", leaderboard)
            return summary
        except BaseException as exc:
            self.journal.summary("failure", {"error": f"{type(exc).__name__}: {exc}", "rounds_completed": len(self.rounds)})
            raise
        finally:
            self.journal.close()
