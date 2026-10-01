from simulation.sdk import BaseBot, Action
from utils.cards import evaluate, RANKS

class Bot(BaseBot):
    def act(self, obs):
        r = sorted((RANKS.index(c[0]) + 2 for c in obs.hole_cards), reverse=True)
        strong = (r[0] == r[1] and r[0] >= 10) or (r[0] == 14 and r[1] >= 12)
        if obs.board: strong = evaluate(obs.hole_cards + obs.board)[0] >= 2
        if strong and "raise" in obs.legal_actions.types:
            return Action("raise", obs.legal_actions.min_raise_to)
        if "check" in obs.legal_actions.types: return Action("check")
        return Action("call" if strong else "fold")
