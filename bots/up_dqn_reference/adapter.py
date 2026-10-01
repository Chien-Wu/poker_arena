from pathlib import Path
from simulation.sdk import BaseBot
from utils.cards import outcome_probabilities
from utils.upstream import basic_environment,load_policy,translate

class Bot(BaseBot):
    def __init__(self,config=None,seed=0):
        super().__init__(config,seed)
        env=basic_environment()
        env.update(BasePokerPlayer=object,gen_cards=lambda cards:[c[1]+c[0].lower() for c in cards])
        def estimate(nb_simulation,nb_player,hole_card,community_card):
            win,lose,tie=outcome_probabilities(hole_card,community_card,opponents=nb_player-1,
                samples=min(nb_simulation,int(self.config['samples'])),rng=self.rng)
            return win+tie  # PyPokerEngine's win test includes tied best hands.
        env['estimate_hole_card_win_rate']=estimate
        self.player=load_policy(Path(__file__).parent,env)['HeuristicPlayer']()

    def act(self,obs):
        la=obs.legal_actions
        valid=[{'action':'fold','amount':0},
               {'action':'call','amount':obs.hero.street_bet+la.call_amount},
               {'action':'raise','amount':{'min':la.min_raise_to or -1,'max':la.max_raise_to or -1}}]
        suit_first=lambda cards:[c[1].upper()+c[0] for c in cards]
        state={'street':obs.street,'community_card':suit_first(obs.board),
               'pot':{'main':{'amount':obs.pot},'side':[]},
               'seats':[{'uuid':p.player_id,'stack':p.stack,'state':p.status} for p in obs.players]}
        self.upstream_calls+=1
        action,amount=self.player.declare_action(valid,suit_first(obs.hole_cards),state)
        return translate(self,obs,action,amount)
