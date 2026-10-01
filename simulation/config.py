"""Strict, serializable experiment configuration and dotted-path overrides."""
from __future__ import annotations
import copy
import json
import secrets
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from .contracts import integer, ContractError


@dataclass
class GameConfig:
    initial_stack: int = 2000
    small_blind: int = 10
    big_blind: int = 20
    ante: int = 0
    hands_per_game: int = 100
    max_actions_per_hand: int = 2000
    # Each entry: {"from_hand": 51, "small_blind": 20, "big_blind": 40, "ante": 0}
    blind_schedule: list[dict] = field(default_factory=list)

    def validate(self):
        for name in ("initial_stack", "small_blind", "big_blind", "hands_per_game", "max_actions_per_hand"):
            integer(getattr(self, name), name, 1)
        integer(self.ante, "ante")
        if self.small_blind > self.big_blind:
            raise ContractError("small_blind must not exceed big_blind")
        previous = 0
        for level in self.blind_schedule:
            if set(level) != {"from_hand", "small_blind", "big_blind", "ante"}:
                raise ContractError("Blind levels need from_hand, small_blind, big_blind, ante")
            integer(level["from_hand"], "from_hand", previous + 1)
            integer(level["small_blind"], "small_blind", 1)
            integer(level["big_blind"], "big_blind", level["small_blind"])
            integer(level["ante"], "ante")
            previous = level["from_hand"]

    def blinds(self, hand_number):
        values = (self.small_blind, self.big_blind, self.ante)
        for level in self.blind_schedule:
            if level["from_hand"] <= hand_number:
                values = level["small_blind"], level["big_blind"], level["ante"]
        return values


@dataclass
class TournamentConfig:
    rounds: int = 4
    group_size: int = 5
    rotation_cycles: int = 1
    regroup: bool = True
    require_equal_groups: bool = False
    tiebreak_hands: int = 20
    tiebreak_attempts: int = 3
    tiebreak_scope: str = "all"  # "final" shares intermediate points for faster research runs
    unresolved_ties: str = "share"  # share occupied-rank points, or error

    def validate(self):
        for name in ("rounds", "rotation_cycles", "tiebreak_hands", "tiebreak_attempts"):
            integer(getattr(self, name), name, 1)
        integer(self.group_size, "group_size", 2)
        if self.group_size > 9: raise ContractError("group_size must not exceed 9")
        if self.tiebreak_scope not in {"all", "final"}: raise ContractError("Invalid tiebreak_scope")
        if self.unresolved_ties not in {"share", "error"}: raise ContractError("Invalid unresolved_ties")
        for name in ("regroup", "require_equal_groups"):
            if type(getattr(self, name)) is not bool: raise ContractError(f"{name} must be a boolean")


@dataclass
class ExecutionConfig:
    runner: str = "subprocess"  # inprocess is trusted-code testing only; docker for isolation
    action_timeout_ms: int = 2000
    startup_timeout_ms: int = 20000
    event_timeout_ms: int = 2000
    max_failures_per_game: int = 3
    failure_policy: str = "check_fold"  # or abort
    memory_mb: int = 2048
    cpu_seconds: int = 120
    require_no_network: bool = False
    docker_image: str = "poker-arena-bot:local"

    def validate(self):
        if self.runner not in {"inprocess", "subprocess", "docker"}: raise ContractError("Unknown runner")
        for name in ("action_timeout_ms", "startup_timeout_ms", "event_timeout_ms",
                     "max_failures_per_game", "memory_mb", "cpu_seconds"):
            integer(getattr(self, name), name, 1)
        if self.failure_policy not in {"check_fold", "abort"}: raise ContractError("Unknown failure policy")
        if type(self.require_no_network) is not bool: raise ContractError("require_no_network must be boolean")
        if self.require_no_network and self.runner != "docker":
            raise ContractError("No-network enforcement requires the docker runner; subprocess is not a sandbox")


@dataclass
class Entry:
    id: str
    bot: str
    params: dict = field(default_factory=dict)


@dataclass
class Config:
    players: list[Entry]
    game: GameConfig = field(default_factory=GameConfig)
    tournament: TournamentConfig = field(default_factory=TournamentConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    seed: int | None = None

    def validate(self):
        import re
        self.game.validate(); self.tournament.validate(); self.execution.validate()
        if len(self.players) < 2: raise ContractError("At least two entries required")
        if len({p.id for p in self.players}) != len(self.players): raise ContractError("Duplicate entry id")
        for p in self.players:
            if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]+", v) for v in (p.id, p.bot)):
                raise ContractError("Player and bot ids may only contain letters, digits, _ and -")
            if not isinstance(p.params, dict): raise ContractError("params must be an object")
            json.dumps(p.params, allow_nan=False)
        if self.seed is not None: integer(self.seed, "seed")
        return self

    def resolved(self):
        result = copy.deepcopy(self).validate()
        if result.seed is None: result.seed = secrets.randbits(128)
        return result

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict): raise ContractError("Configuration must be an object")
        def build(kind, raw):
            if not isinstance(raw, dict): raise ContractError(f"{kind.__name__} must be an object")
            unknown = set(raw) - {f.name for f in fields(kind)}
            if unknown: raise ContractError(f"Unknown {kind.__name__} fields: {sorted(unknown)}")
            return kind(**raw)
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown: raise ContractError(f"Unknown config fields: {sorted(unknown)}")
        return cls([build(Entry, p) for p in data.get("players", [])],
                   build(GameConfig, data.get("game", {})),
                   build(TournamentConfig, data.get("tournament", {})),
                   build(ExecutionConfig, data.get("execution", {})), data.get("seed")).validate()

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text()))


def set_path(data, path, value):
    parts = path.split(".")
    target = data
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    if isinstance(target, list): target[int(parts[-1])] = value
    else: target[parts[-1]] = value


def override(config: Config, expressions: list[str]) -> Config:
    data = config.to_dict()
    for expression in expressions:
        if "=" not in expression: raise ContractError("Overrides use path=value")
        path, raw = expression.split("=", 1)
        try: value = json.loads(raw)
        except json.JSONDecodeError: value = raw
        set_path(data, path, value)
    return Config.from_dict(data)
