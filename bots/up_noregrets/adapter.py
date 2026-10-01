from pathlib import Path
from types import SimpleNamespace as NS,MethodType
import json
from simulation.sdk import BaseBot
from utils.cards import RANKS,SUITS
from utils.upstream import numpy_environment,load_policy,translate

class Bot(BaseBot):
    def __init__(self,config=None,seed=0):
        super().__init__(config,seed)
        ns=load_policy(Path(__file__).parent,numpy_environment())
        self.ns=ns
        table={}
        if self.config.get('blueprint'):
            path=(Path(__file__).parent/'code'/self.config['blueprint']).resolve()
            if not path.is_relative_to((Path(__file__).parent/'code').resolve()):
                raise ValueError('Blueprint must be inside this bot/code directory')
            raw=json.loads(path.read_text())
            for key,actions in raw.items():
                table[key]={(ns['Action'][a['action']],int(a['amount'])):float(a['weight']) for a in actions}
        getter=ns['get_average_strategy']
        blueprint=NS(strategy_sum=table)
        blueprint.get_average_strategy=MethodType(getter,blueprint)
        self.player=NS(blueprint=blueprint)
        for name in ('get_action','_get_info_set','_encode_betting_history','_sample_from_strategy'):
            setattr(self.player,name,MethodType(ns[name],self.player))

    def act(self,obs):
        # Card integers are suit-major, rank 0..12. Hidden cards are NOT filled.
        card=lambda c:SUITS.index(c[1])*13+RANKS.index(c[0])
        state=NS(pot=obs.pot,players_in_hand={p.seat for p in obs.players if p.status in ('active','all_in')},
                 current_player=obs.hero_seat,board_cards=[card(c) for c in obs.board],
                 betting_round={'preflop':0,'flop':1,'turn':2,'river':3}[obs.street],
                 last_bet=obs.hero.street_bet+obs.to_call,
                 player_bets={p.seat:p.street_bet for p in obs.players},
                 player_chips={p.seat:p.stack for p in obs.players},
                 hole_cards={obs.hero_seat:[card(c) for c in obs.hole_cards]})
        self.upstream_calls+=1
        action,amount=self.player.get_action(state,obs.hero_seat,use_search=False)
        return translate(self,obs,action.name.lower(),amount)
