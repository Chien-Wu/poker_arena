from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import SimpleNamespace as NS
from simulation.sdk import BaseBot
from utils.cards import evaluate
from utils.upstream import basic_environment,load_policy,rich_cards,install_module,translate

class Street(str,Enum):
    PREFLOP='preflop';FLOP='flop';TURN='turn';RIVER='river'
class Type(str,Enum):
    FOLD='fold';CHECK='check';CALL='call';BET='bet';RAISE='raise';ALL_IN='all_in'
class Abstract(str,Enum):
    FOLD='fold';CHECK='check';CALL='call';BET_33='bet_33';BET_75='bet_75';BET_125='bet_125'
    RAISE_2_5X='raise_2_5x';RAISE_4X='raise_4x';ALL_IN='all_in'
@dataclass(frozen=True)
class LegacyAction:
    action_type:Type
    amount:int=0
class Agent:
    def __init__(self,name='Agent'):self.name=name

class Bot(BaseBot):
    def __init__(self,config=None,seed=0):
        super().__init__(config,seed)
        install_module('holdem.engine.hand_eval',best_hand=lambda cards:(evaluate([str(c) for c in cards]),None),
            STRAIGHT_FLUSH=8,FOUR_OF_A_KIND=7,FULL_HOUSE=6,FLUSH=5,STRAIGHT=4,
            THREE_OF_A_KIND=3,TWO_PAIR=2,ONE_PAIR=1)
        env=basic_environment()
        env.update(Street=Street,ActionType=Type,AbstractAction=Abstract,Action=LegacyAction,
                   Agent=Agent,PlayerObservation=NS)
        self.player=load_policy(Path(__file__).parent,env)['RuleBasedHeuristicAgent'](seed=seed)

    def on_hand_start(self,obs):self.player.reset()

    def act(self,obs):
        legal=[]
        for kind in obs.legal_actions.types:
            if kind!='raise':legal.append(LegacyAction(Type(kind),obs.legal_actions.call_amount if kind=='call' else 0))
        if 'raise' in obs.legal_actions.types:
            lower,upper=obs.legal_actions.min_raise_to,obs.legal_actions.max_raise_to
            wager=obs.hero.street_bet+obs.to_call
            targets={lower,upper,*[int(obs.pot*f) for f in (.33,.75,1.25)],int(wager*2.5),wager*4}
            # Reconstruct the legal menu used by this policy vocabulary, not a
            # fictitious opponent hand or an unrestricted engine State object.
            for target in sorted({max(lower,min(upper,t)) for t in targets}):
                legal.append(LegacyAction(Type.RAISE if obs.to_call else Type.BET,target))
            legal.append(LegacyAction(Type.ALL_IN,upper))
        elif obs.legal_actions.call_amount==obs.hero.stack and obs.to_call:
            legal.append(LegacyAction(Type.ALL_IN,obs.hero.street_bet+obs.hero.stack))
        opponent=obs.players[1-obs.hero_seat]
        view=NS(seat=obs.hero_seat,hand_id=obs.hand_number,hole_cards=rich_cards(obs.hole_cards),
                board=rich_cards(obs.board),stack=obs.hero.stack,opponent_stack=opponent.stack,
                pot=obs.pot,to_call=obs.to_call,street_contribution=obs.hero.street_bet,
                street=Street(obs.street),acting_player=obs.hero_seat,dealer_seat=obs.button_seat,
                action_history=[(e.seat,e.action) for e in obs.history if e.type=='action'],
                legal_actions=legal,legal_abstract_actions=list(Abstract))
        self.upstream_calls+=1
        result=self.player.act(view)
        return translate(self,obs,result.action_type.value,result.amount)
