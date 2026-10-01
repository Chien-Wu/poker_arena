from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import SimpleNamespace as NS
import logging
from simulation.sdk import BaseBot
from utils.cards import RANKS, SUITS, outcome_probabilities
from utils.upstream import numpy_environment,load_policy,translate

class Kind(Enum):
    Fold=0; Check=1; Call=2; Raise=3
@dataclass
class LegacyAction:
    action:Kind
    amount:float=0
@dataclass
class EvalCard:
    rank:int
    suit:str
    def __str__(self):return RANKS[self.rank-2]+{'clubs':'c','diamonds':'d','hearts':'h','spades':'s'}[self.suit]

def cards(values):return [NS(rank=RANKS.index(c[0]),suit=SUITS.index(c[1])) for c in values]

class Bot(BaseBot):
    def __init__(self,config=None,seed=0):
        super().__init__(config,seed)
        env=numpy_environment()
        env.update(pkrs=NS(ActionEnum=Kind,Action=LegacyAction),EvalCard=EvalCard,logging=logging)
        env['get_mcts_result']=lambda player_id,hand,board,n_simulations=1000,n_opponents=2,verbose=False: outcome_probabilities(
            [str(c) for c in hand],[str(c) for c in board],opponents=n_opponents,
            samples=min(n_simulations,int(self.config['samples'])),rng=self.rng)
        self.cls=load_policy(Path(__file__).parent,env)['RandomAgent_mcts']
        self.player=None

    def on_hand_start(self,obs):
        self.player=self.cls(obs.hero_seat)

    def act(self,obs):
        if self.player is None:self.on_hand_start(obs)
        ps=[NS(player=p.seat,hand=cards(obs.hole_cards) if p.seat==obs.hero_seat else [],
               bet_chips=p.street_bet,pot_chips=p.total_contribution-p.street_bet,
               stake=p.stack,active=p.status in ('active','all_in')) for p in obs.players]
        kinds={'fold':Kind.Fold,'check':Kind.Check,'call':Kind.Call,'raise':Kind.Raise}
        state=NS(current_player=obs.hero_seat,players_state=ps,public_cards=cards(obs.board),
                 stage={'preflop':0,'flop':1,'turn':2,'river':3}[obs.street],pot=obs.pot,
                 min_bet=obs.hero.street_bet+obs.to_call,
                 from_action=None if not any(e.type=='action' for e in obs.history) else NS(),
                 legal_actions=[kinds[k] for k in obs.legal_actions.types])
        self.upstream_calls+=1
        a,_=self.player.choose_action(state,verbose=False)
        return translate(self,obs,a.action.name.lower(),a.amount,amount_mode='raise_by')
