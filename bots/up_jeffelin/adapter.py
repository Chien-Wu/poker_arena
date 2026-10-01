from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace as NS
from simulation.sdk import BaseBot
from utils.upstream import basic_environment, load_policy, translate

@dataclass(frozen=True)
class FoldAction: pass
@dataclass(frozen=True)
class CheckAction: pass
@dataclass(frozen=True)
class CallAction: pass
@dataclass(frozen=True)
class RaiseAction: amount: int
@dataclass(frozen=True)
class DiscardAction: index: int

class Bot(BaseBot):
    def __init__(self, config=None, seed=0):
        super().__init__(config, seed)
        env = basic_environment()
        env.update(Bot=object, FoldAction=FoldAction, CheckAction=CheckAction,
                   CallAction=CallAction, RaiseAction=RaiseAction, DiscardAction=DiscardAction)
        self.player = load_policy(Path(__file__).parent, env)['Player']()

    def state(self, obs):
        # Original policy is heads-up; the registry rejects other table sizes.
        hands = [[], []]; hands[obs.hero_seat] = list(obs.hole_cards)
        classes = {'fold':FoldAction, 'check':CheckAction, 'call':CallAction, 'raise':RaiseAction}
        state = NS(button=obs.button_seat, street={'preflop':0,'flop':3,'turn':4,'river':5}[obs.street],
                   pips=[p.street_bet for p in obs.players], stacks=[p.stack for p in obs.players],
                   hands=hands, board=list(obs.board), previous_state=None,
                   legal_actions=lambda: {classes[k] for k in obs.legal_actions.types},
                   raise_bounds=lambda: (obs.legal_actions.min_raise_to, obs.legal_actions.max_raise_to))
        game = NS(bankroll=0, game_clock=obs.action_timeout_ms / 1000, round_num=obs.hand_number)
        return game, state

    def on_hand_start(self, obs):
        game, state = self.state(obs)
        self.player.handle_new_round(game, state, obs.hero_seat)

    def act(self, obs):
        game, state = self.state(obs)
        self.upstream_calls += 1
        action = self.player.get_action(game, state, obs.hero_seat)
        types = {FoldAction:'fold', CheckAction:'check', CallAction:'call', RaiseAction:'raise'}
        if type(action) not in types: raise ValueError('Discard actions are outside this NLHE projection')
        return translate(self, obs, types[type(action)], getattr(action, 'amount', None))
