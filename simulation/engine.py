"""Integer-chip, 2–9 seat no-limit Hold'em state machine.

Supported rules profile: nlhe-moving-button-v1, no rake, one board, uniform ante,
full-raise reopening (including cumulative short all-ins), no rebuys within a game.
This is an offline research engine, not an implementation of live-dealer procedures.
"""
from __future__ import annotations
from dataclasses import asdict
import random
from typing import Sequence
from .contracts import (
    Action, ContractError, Event, HandResult, LegalActions, Observation,
    PlayerView, PotView, SCHEMA_VERSION, STREETS, integer,
)
from utils.cards import DECK, evaluate, validate_cards


class Hand:
    def __init__(self, player_ids: Sequence[str], stacks: Sequence[int], *, button: int,
                 small_blind: int = 10, big_blind: int = 20, ante: int = 0,
                 seed: int = 0, deck: Sequence[str] | None = None,
                 game_id: str = "game", hand_number: int = 1,
                 action_timeout_ms: int = 2000, hands_remaining: int = 0):
        if not 2 <= len(player_ids) <= 9 or len(stacks) != len(player_ids):
            raise ValueError("Need 2–9 seats and one stack per seat")
        if len(set(player_ids)) != len(player_ids):
            raise ValueError("player_ids must be unique")
        for x in stacks: integer(x, "stack")
        integer(small_blind, "small_blind", 1)
        integer(big_blind, "big_blind", small_blind)
        integer(ante, "ante")
        integer(button, "button")
        if button >= len(stacks) or stacks[button] == 0:
            raise ValueError("Button must be an occupied seat")
        if sum(x > 0 for x in stacks) < 2:
            raise ValueError("At least two non-busted players are required")
        self.player_ids = tuple(player_ids)
        self.starting_stacks = tuple(stacks)
        self.stacks = list(stacks)
        self.n = len(stacks)
        self.button = button
        self.small_blind, self.big_blind, self.ante = small_blind, big_blind, ante
        self.game_id, self.hand_number = game_id, hand_number
        self.hand_id = f"{game_id}:h{hand_number}"
        self.action_timeout_ms = action_timeout_ms
        self.hands_remaining = hands_remaining
        self.seed = seed
        self._deck = list(deck) if deck is not None else list(DECK)
        if len(self._deck) != 52 or set(validate_cards(self._deck)) != set(DECK):
            raise ValueError("Deck must be a permutation of all 52 canonical cards")
        if deck is None:
            random.Random(seed).shuffle(self._deck)
        self.initial_deck = tuple(self._deck)
        self._deck_index = 0
        self._hole_cards: dict[int, list[str]] = {i: [] for i, x in enumerate(stacks) if x > 0}
        self.board: list[str] = []
        self.folded = [x == 0 for x in stacks]
        self.street_bets = [0] * self.n
        self.contributions = [0] * self.n
        self.acted_at: list[int | None] = [None] * self.n
        self.street_index = 0
        self.current_bet = big_blind
        self.last_full_raise = big_blind
        self.history: list[Event] = []
        self.actions: list[dict] = []
        self.pot_results: list[dict] = []
        self.terminal = False
        self.showdown = False
        self.actor: int | None = None
        live = self.live_seats
        self.sb_seat = button if len(live) == 2 else self.next_seat(button, live)
        self.bb_seat = self.next_seat(self.sb_seat, live)
        # Deal one card at a time, beginning left of the button.
        order = self.cyclic_after(button, live)
        for _ in range(2):
            for seat in order:
                self._hole_cards[seat].append(self._draw())
        for seat in live:
            if ante:
                paid = self._pay(seat, min(ante, self.stacks[seat]), street=False)
                self._event("ante", seat=seat, paid=paid)
        for seat, amount in ((self.sb_seat, small_blind), (self.bb_seat, big_blind)):
            paid = self._pay(seat, min(amount, self.stacks[seat]))
            self._event("blind", seat=seat, paid=paid)
        self.pending = set(self.actionable_seats)
        self._advance(self.bb_seat)
        self.assert_invariants()

    @property
    def street(self) -> str:
        return STREETS[self.street_index]

    @property
    def live_seats(self) -> list[int]:
        return [i for i in range(self.n) if not self.folded[i]]

    @property
    def actionable_seats(self) -> list[int]:
        return [i for i in self.live_seats if self.stacks[i] > 0]

    @property
    def pot(self) -> int:
        return sum(self.contributions)

    def cyclic_after(self, seat: int, eligible) -> list[int]:
        eligible = set(eligible)
        return [i for offset in range(1, self.n + 1)
                if (i := (seat + offset) % self.n) in eligible]

    def next_seat(self, seat: int, eligible) -> int:
        ordered = self.cyclic_after(seat, eligible)
        if not ordered: raise ValueError("No eligible next seat")
        return ordered[0]

    def _draw(self) -> str:
        if self._deck_index >= len(self._deck):
            raise RuntimeError("Deck exhausted")
        card = self._deck[self._deck_index]
        self._deck_index += 1
        return card

    def _pay(self, seat: int, amount: int, *, street: bool = True) -> int:
        if not 0 <= amount <= self.stacks[seat]:
            raise RuntimeError("Internal overdraft")
        self.stacks[seat] -= amount
        self.contributions[seat] += amount
        if street: self.street_bets[seat] += amount
        return amount

    def _event(self, type: str, **data) -> None:
        self.history.append(Event(len(self.history), type, self.street, **data))

    def _target(self, seat: int) -> int:
        # A player alone against all-ins cannot be forced to build a dry side pot.
        if len(self.actionable_seats) <= 1:
            return max((self.street_bets[i] for i in self.live_seats if i != seat), default=0)
        return self.current_bet

    def legal_actions(self, seat: int | None = None) -> LegalActions:
        seat = self.actor if seat is None else seat
        if self.terminal or seat is None or seat != self.actor:
            return LegalActions((), 0, 0, None, None, None)
        target = self._target(seat)
        owed = max(0, target - self.street_bets[seat])
        types = ["fold", "call" if owed else "check"]
        minimum = maximum = full_minimum = None
        # A short all-in does not reopen action unless the cumulative increment
        # now faced is at least the last full bet/raise increment.
        reopened = self.acted_at[seat] is None or self.current_bet - self.acted_at[seat] >= self.last_full_raise
        if reopened and len(self.actionable_seats) >= 2:
            max_to = self.street_bets[seat] + self.stacks[seat]
            if max_to > self.current_bet:
                full_minimum = self.current_bet + self.last_full_raise
                minimum = min(full_minimum, max_to)
                maximum = max_to
                types.append("raise")
        return LegalActions(tuple(types), owed, min(owed, self.stacks[seat]),
                            minimum, maximum, full_minimum,
                            minimum is not None and minimum < full_minimum)

    def apply(self, action: Action) -> None:
        if self.terminal or self.actor is None:
            raise ContractError("No action expected")
        if not isinstance(action, Action):
            raise ContractError("Expected canonical Action")
        legal = self.legal_actions()
        legal.validate(action)  # Validate BEFORE any mutation.
        seat = self.actor
        self.actions.append({"seat": seat, "action": action.to_dict()})
        self.pending.discard(seat)
        paid = 0
        if action.type == "fold":
            self.folded[seat] = True
        elif action.type == "call":
            paid = self._pay(seat, legal.call_amount)
            self.acted_at[seat] = self.current_bet
        elif action.type == "check":
            self.acted_at[seat] = self.current_bet
        else:
            old_target = self.current_bet
            paid = self._pay(seat, action.raise_to - self.street_bets[seat])
            self.current_bet = action.raise_to
            increment = self.current_bet - old_target
            if increment >= self.last_full_raise:
                self.last_full_raise = increment
            self.acted_at[seat] = self.current_bet
            self.pending.update(i for i in self.actionable_seats
                                if i != seat and self.street_bets[i] < self.current_bet)
        self._event("action", seat=seat, action=action.type, paid=paid, raise_to=action.raise_to)
        self._advance(seat)
        self.assert_invariants()

    def _refund_uncalled(self) -> None:
        bets = sorted(((bet, i) for i, bet in enumerate(self.street_bets)), reverse=True)
        if not bets or bets[0][0] <= bets[1][0]:
            return
        highest, seat = bets[0]
        if self.folded[seat]:
            raise RuntimeError("Folded player has an unmatched highest wager")
        refund = highest - bets[1][0]
        self.stacks[seat] += refund
        self.contributions[seat] -= refund
        self.street_bets[seat] -= refund
        self._event("refund", seat=seat, paid=refund)

    def _advance(self, after: int) -> None:
        while not self.terminal:
            live = self.live_seats
            if len(live) == 1:
                self._refund_uncalled()
                self._finish_without_showdown(live[0])
                return
            self.pending.intersection_update(self.actionable_seats)
            if len(self.actionable_seats) <= 1:
                self.pending = {i for i in self.actionable_seats
                                if self.street_bets[i] < self._target(i)}
            if self.pending:
                self.actor = self.next_seat(after, self.pending)
                return
            self._refund_uncalled()
            if self.street_index == 3:
                self._showdown()
                return
            self.street_index += 1
            self.street_bets = [0] * self.n
            self.current_bet = 0
            self.last_full_raise = self.big_blind
            self.acted_at = [None] * self.n
            self._draw()  # Burn, never included in a player observation/event.
            new_cards = tuple(self._draw() for _ in range(3 if self.street_index == 1 else 1))
            self.board.extend(new_cards)
            self._event("board", cards=new_cards)
            self.pending = set(self.actionable_seats)
            after = self.button

    def _finish_without_showdown(self, winner: int) -> None:
        amount = self.pot
        self.pot_results = [{"amount": amount, "eligible_seats": [winner], "winners": [winner],
                             "awards": {str(winner): amount}}]
        self.stacks[winner] += amount
        self.contributions = [0] * self.n
        self.street_bets = [0] * self.n
        self.actor = None
        self.terminal = True

    def pot_views(self) -> tuple[PotView, ...]:
        levels = sorted({x for x in self.contributions if x > 0})
        previous = 0
        pots = []
        for level in levels:
            contributors = [i for i, amount in enumerate(self.contributions) if amount >= level]
            eligible = tuple(i for i in contributors if not self.folded[i])
            amount = (level - previous) * len(contributors)
            # Folded contributors can introduce a tier without changing who
            # may win it. Merge those tiers BEFORE splitting odd chips; splitting
            # two odd sub-tiers separately can otherwise award two odd chips to
            # the same seat when the combined pot is even.
            if pots and pots[-1].eligible_seats == eligible:
                pots[-1] = PotView(pots[-1].amount + amount, eligible)
            else:
                pots.append(PotView(amount, eligible))
            previous = level
        return tuple(pots)

    def _showdown(self) -> None:
        self.showdown = True
        scores = {i: evaluate(tuple(self._hole_cards[i]) + tuple(self.board)) for i in self.live_seats}
        self.pot_results = []
        for pot in self.pot_views():
            if not pot.eligible_seats:
                raise RuntimeError("Side pot has no eligible live player")
            best = max(scores[i] for i in pot.eligible_seats)
            winners = self.cyclic_after(self.button, [i for i in pot.eligible_seats if scores[i] == best])
            base, odd = divmod(pot.amount, len(winners))
            awards = {str(i): base + (offset < odd) for offset, i in enumerate(winners)}
            for i in winners: self.stacks[i] += awards[str(i)]
            self.pot_results.append({"amount": pot.amount, "eligible_seats": list(pot.eligible_seats),
                                     "winners": winners, "awards": awards})
        self.contributions = [0] * self.n
        self.street_bets = [0] * self.n
        self.terminal = True
        self.actor = None

    def observation(self, seat: int) -> Observation:
        if seat not in self._hole_cards:
            raise ValueError("Busted seat was not dealt a hand")
        views = []
        for i in range(self.n):
            status = ("out" if self.starting_stacks[i] == 0 else "folded" if self.folded[i]
                      else "all_in" if self.stacks[i] == 0 else "active")
            views.append(PlayerView(i, self.player_ids[i], self.stacks[i], self.starting_stacks[i],
                                    self.street_bets[i], self.contributions[i], status))
        return Observation(SCHEMA_VERSION, self.game_id, self.hand_id, self.hand_number, seat,
                           self.button, self.sb_seat, self.bb_seat, self.street,
                           tuple(self._hole_cards[seat]), tuple(self.board), tuple(views),
                           self.pot, self.pot_views(), self.legal_actions(seat), tuple(self.history),
                           self.small_blind, self.big_blind, self.ante, self.action_timeout_ms,
                           self.hands_remaining)

    def result(self) -> HandResult:
        if not self.terminal:
            raise RuntimeError("Hand has not finished")
        shown = tuple((i, tuple(self._hole_cards[i])) for i in self.live_seats) if self.showdown else ()
        return HandResult(self.hand_id, self.hand_number, tuple(self.board), self.starting_stacks,
                          tuple(self.stacks), tuple(b - a for a, b in zip(self.starting_stacks, self.stacks)),
                          shown, tuple(self.pot_results), tuple(self.history))

    def replay_record(self) -> dict:
        if not self.terminal: raise RuntimeError("Only completed hands are logged")
        return {"schema_version": 1, "rules_profile": "nlhe-moving-button-v1",
                "game_id": self.game_id, "hand_number": self.hand_number,
                "player_ids": self.player_ids, "starting_stacks": self.starting_stacks,
                "button": self.button, "small_blind": self.small_blind,
                "big_blind": self.big_blind, "ante": self.ante,
                "deck": self.initial_deck, "actions": self.actions,
                "result": asdict(self.result())}

    def assert_invariants(self) -> None:
        if any(type(x) is not int or x < 0 for x in self.stacks + self.contributions + self.street_bets):
            raise AssertionError("Chips must remain nonnegative integers")
        if sum(self.stacks) + self.pot != sum(self.starting_stacks):
            raise AssertionError("Chip conservation failed")
        if any(b > c for b, c in zip(self.street_bets, self.contributions)):
            raise AssertionError("Street contribution exceeds total contribution")
        dealt = [c for hand in self._hole_cards.values() for c in hand] + self.board
        if len(set(dealt)) != len(dealt):
            raise AssertionError("Duplicate dealt card")
        if not self.terminal and self.actor not in self.actionable_seats:
            raise AssertionError("Actor must have a live hand and chips")
