"""Small SDK. A bot only needs to implement BaseBot.act()."""
from __future__ import annotations
import random
from typing import Any
from .contracts import Action, Observation, Event, GameContext, HandResult


class BaseBot:
    def __init__(self, config: dict[str, Any] | None = None, seed: int = 0):
        self.config = dict(config or {})
        self.rng = random.Random(seed)
        self.seed = seed
        self.upstream_calls = 0
        self.adapter_repairs = 0

    def on_game_start(self, context: GameContext) -> None:
        pass

    def on_hand_start(self, observation: Observation) -> None:
        pass

    def on_event(self, event: Event) -> None:
        pass

    def act(self, observation: Observation) -> Action:
        raise NotImplementedError

    def on_hand_end(self, result: HandResult) -> None:
        pass

    def on_game_end(self, result: dict) -> None:
        pass

    def close(self) -> None:
        pass
