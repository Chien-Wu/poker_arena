"""Canonical interface -> the strategy you edit in code/strategy.py."""
from simulation.sdk import BaseBot
from .code.strategy import decide


class Bot(BaseBot):
    def act(self, observation):
        return decide(observation, self.config, self.rng)
