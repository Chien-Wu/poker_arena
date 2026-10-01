from simulation.sdk import BaseBot, Action

class Bot(BaseBot):
    def act(self, obs):
        return Action("check" if "check" in obs.legal_actions.types else "call")
