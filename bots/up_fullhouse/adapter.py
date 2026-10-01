from pathlib import Path
from simulation.sdk import BaseBot
from utils.upstream import basic_environment,load_policy,translate

class Bot(BaseBot):
    def __init__(self,config=None,seed=0):
        super().__init__(config,seed)
        self.policy=load_policy(Path(__file__).parent,basic_environment())['decide']

    def act(self,obs):
        state={'street':obs.street,'amount_owed':obs.to_call,'pot':obs.pot,
               'your_stack':obs.hero.stack,'seat_to_act':obs.hero_seat,
               'players':[{'seat':p.seat,'stack':p.stack,'status':p.status} for p in obs.players],
               'your_cards':list(obs.hole_cards),'board':list(obs.board),
               'your_bet_this_street':obs.hero.street_bet,
               'min_raise_to':obs.legal_actions.min_raise_to or obs.hero.street_bet+obs.to_call+obs.big_blind,
               'can_check':'check' in obs.legal_actions.types}
        self.upstream_calls+=1
        result=self.policy(state)
        return translate(self,obs,result['action'],result.get('amount'))
