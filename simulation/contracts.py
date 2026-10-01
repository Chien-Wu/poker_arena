"""Versioned, JSON-safe public bot contract. No engine objects cross this boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1
ACTION_TYPES = frozenset({"fold", "check", "call", "raise"})
STREETS = ("preflop", "flop", "turn", "river")


class ContractError(ValueError):
    pass


def integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ContractError(f"{name} must be an integer >= {minimum}; got {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class Action:
    type: str
    raise_to: int | None = None

    def __post_init__(self) -> None:
        if self.type not in ACTION_TYPES:
            raise ContractError(f"Unknown action type: {self.type!r}")
        if self.type == "raise":
            integer(self.raise_to, "raise_to", 1)
        elif self.raise_to is not None:
            raise ContractError("Only a raise may contain raise_to")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.raise_to is not None:
            result["raise_to"] = self.raise_to
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Action:
        if not isinstance(value, dict) or set(value) - {"type", "raise_to"}:
            raise ContractError("Action must contain only type and optional raise_to")
        if not isinstance(value.get("type"), str):
            raise ContractError("Action.type is required and must be a string")
        return cls(value["type"], value.get("raise_to"))


@dataclass(frozen=True, slots=True)
class LegalActions:
    types: tuple[str, ...]
    to_call: int                     # Uncapped amount to match the current wager.
    call_amount: int                 # min(to_call, remaining hero stack).
    min_raise_to: int | None          # Smallest legal total STREET contribution.
    max_raise_to: int | None          # Hero street contribution + remaining stack.
    full_min_raise_to: int | None     # Nominal full-raise minimum, before all-in cap.
    short_all_in_only: bool = False

    def validate(self, action: Action) -> None:
        if action.type not in self.types:
            raise ContractError(f"{action.type} is illegal; legal types: {self.types}")
        if action.type == "raise":
            if self.min_raise_to is None or self.max_raise_to is None:
                raise ContractError("No raise bounds at this node")
            if not self.min_raise_to <= action.raise_to <= self.max_raise_to:
                raise ContractError(
                    f"raise_to={action.raise_to} outside "
                    f"[{self.min_raise_to}, {self.max_raise_to}]"
                )


@dataclass(frozen=True, slots=True)
class PlayerView:
    seat: int
    player_id: str
    stack: int
    starting_stack: int
    street_bet: int
    total_contribution: int
    status: str                       # active / folded / all_in / out


@dataclass(frozen=True, slots=True)
class PotView:
    amount: int
    eligible_seats: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Event:
    sequence: int
    type: str                        # blind / ante / action / board / refund
    street: str
    seat: int | None = None
    action: str | None = None
    paid: int = 0
    raise_to: int | None = None
    cards: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict) -> Event:
        data = dict(data)
        data["cards"] = tuple(data.get("cards", ()))
        return cls(**data)


@dataclass(frozen=True, slots=True)
class Observation:
    schema_version: int
    game_id: str
    hand_id: str
    hand_number: int
    hero_seat: int
    button_seat: int
    small_blind_seat: int
    big_blind_seat: int
    street: str
    hole_cards: tuple[str, str]
    board: tuple[str, ...]
    players: tuple[PlayerView, ...]
    pot: int
    pots: tuple[PotView, ...]
    legal_actions: LegalActions
    history: tuple[Event, ...]
    small_blind: int
    big_blind: int
    ante: int
    action_timeout_ms: int
    hands_remaining: int

    @property
    def to_call(self) -> int:
        """Uncapped amount owed; use legal_actions.call_amount for actual chips."""
        return self.legal_actions.to_call

    @property
    def hero(self) -> PlayerView:
        return self.players[self.hero_seat]

    @property
    def opponents(self) -> tuple[PlayerView, ...]:
        return tuple(p for p in self.players if p.seat != self.hero_seat
                     and p.status in {"active", "all_in"})

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Observation:
        d = dict(data)
        if d.get("schema_version") != SCHEMA_VERSION:
            raise ContractError("Unsupported observation schema")
        d["hole_cards"] = tuple(d["hole_cards"])
        d["board"] = tuple(d["board"])
        d["players"] = tuple(PlayerView(**p) for p in d["players"])
        d["pots"] = tuple(PotView(p["amount"], tuple(p["eligible_seats"])) for p in d["pots"])
        d["history"] = tuple(Event.from_dict(e) for e in d["history"])
        legal = dict(d["legal_actions"])
        legal["types"] = tuple(legal["types"])
        d["legal_actions"] = LegalActions(**legal)
        return cls(**d)


@dataclass(frozen=True, slots=True)
class GameContext:
    schema_version: int
    game_id: str
    player_id: str
    seat: int
    player_ids: tuple[str, ...]
    small_blind: int
    big_blind: int
    ante: int
    initial_stack: int
    hands_per_game: int

    @classmethod
    def from_dict(cls, data: dict) -> GameContext:
        d = dict(data)
        d["player_ids"] = tuple(d["player_ids"])
        return cls(**d)


@dataclass(frozen=True, slots=True)
class HandResult:
    hand_id: str
    hand_number: int
    board: tuple[str, ...]
    starting_stacks: tuple[int, ...]
    final_stacks: tuple[int, ...]
    payoffs: tuple[int, ...]
    shown_cards: tuple[tuple[int, tuple[str, ...]], ...]
    pots: tuple[dict, ...]
    history: tuple[Event, ...]

    @classmethod
    def from_dict(cls, data: dict) -> HandResult:
        d = dict(data)
        for key in ("board", "starting_stacks", "final_stacks", "payoffs", "pots"):
            d[key] = tuple(d[key])
        d["shown_cards"] = tuple((x[0], tuple(x[1])) for x in d["shown_cards"])
        d["history"] = tuple(Event.from_dict(e) for e in d["history"])
        return cls(**d)
