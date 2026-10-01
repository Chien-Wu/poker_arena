from simulation.sdk import BaseBot, Action

class Bot(BaseBot):
    def act(self, obs):
        legal = obs.legal_actions
        kind = self.rng.choice(legal.types)
        if kind == "raise":
            # Log-uniform-ish preset sizing, rather than almost always huge uniform raises.
            target = self.rng.choice((legal.min_raise_to, legal.max_raise_to,
                                     max(legal.min_raise_to, min(legal.max_raise_to, obs.pot))))
            return Action(kind, target)
        return Action(kind)
