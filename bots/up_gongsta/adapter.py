from pathlib import Path
from simulation.sdk import BaseBot
from utils.cards import equity
from utils.upstream import numpy_environment, load_policy, translate

class Bot(BaseBot):
    def __init__(self, config=None, seed=0):
        super().__init__(config, seed)
        env = numpy_environment()
        env['calculate_equity'] = lambda hole, board: equity(hole,board,opponents=1,
            samples=int(self.config['samples']),rng=self.rng)
        self.policy = load_policy(Path(__file__).parent,env)['get_action']

    def act(self, obs):
        self.upstream_calls += 1
        raw = str(self.policy(None, list(obs.hole_cards), list(obs.board), obs.pot,
                     obs.hero.street_bet+obs.to_call, obs.big_blind,
                     obs.hero.stack+obs.hero.street_bet, obs.hero_seat==obs.button_seat,
                     'check' in obs.legal_actions.types))
        if raw.startswith('b'):
            return translate(self,obs,'raise',int(raw[1:]))
        return translate(self,obs,raw)
