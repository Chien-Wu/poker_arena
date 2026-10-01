from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from random import Random
from types import SimpleNamespace as NS
from simulation.sdk import BaseBot
from utils.cards import evaluate
from utils.upstream import basic_environment, load_policy, translate

class View(NS): pass
class Kind(str,Enum):
    FOLD='fold'; CHECK='check'; CALL='call'; RAISE='raise'
@dataclass
class LegacyAction:
    kind: Kind
    raise_to: int|None=None

class Bot(BaseBot):
    def __init__(self, config=None, seed=0):
        super().__init__(config,seed)
        env = basic_environment()
        env.update(Observation=View,ActionKind=Kind,Action=LegacyAction,Random=Random,hand_value=evaluate)
        ns=load_policy(Path(__file__).parent,env)
        style=ns['STYLES'][self.config.get('style','tight_aggressive')]
        self.player=ns['StylePolicy'](style,seed)

    def act(self,obs):
        legal=NS(kinds=tuple(Kind(k) for k in obs.legal_actions.types),
                 call_amount=obs.legal_actions.call_amount,min_raise_to=obs.legal_actions.min_raise_to,
                 max_raise_to=obs.legal_actions.max_raise_to)
        view=View(hole_cards=obs.hole_cards, board=obs.board, pot=obs.pot,
                  legal_actions=legal, players=obs.players, finished=False,
                  actor=obs.hero_seat,seat=obs.hero_seat)
        self.upstream_calls+=1
        a=self.player.choose_action(view)
        return translate(self,obs,a.kind.value,a.raise_to)
