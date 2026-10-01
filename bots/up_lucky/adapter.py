from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace as NS
from simulation.sdk import BaseBot
from utils.cards import DECK, evaluate
from utils.upstream import basic_environment, load_policy, position, translate

@dataclass
class LegacyAction:
    type: str
    amount: int | None = None

class Bot(BaseBot):
    def __init__(self, config=None, seed=0):
        super().__init__(config, seed)
        env = basic_environment()
        env.update(Action=LegacyAction, PlayerView=NS,
                   _FULL_DECK=[tuple(c) for c in DECK],
                   eval_hand=lambda hole, board: evaluate([''.join(c) for c in [*hole, *board]]))
        cls = load_policy(Path(__file__).parent, env)['MonteCarloBot']
        self.player = cls(simulations=int(self.config['samples']))

    def act(self, obs):
        actions = []
        for kind in obs.legal_actions.types:
            if kind == 'raise':
                actions.append(dict(type='bet' if obs.to_call == 0 else 'raise',
                                    min=obs.legal_actions.min_raise_to, max=obs.legal_actions.max_raise_to))
            else: actions.append(dict(type=kind))
        view = NS(me=obs.hero.player_id, street=obs.street, position=position(obs),
                  hole_cards=[tuple(c) for c in obs.hole_cards], board=[tuple(c) for c in obs.board],
                  pot=obs.pot, to_call=obs.to_call, min_raise=obs.legal_actions.min_raise_to,
                  max_raise=obs.legal_actions.max_raise_to, legal_actions=actions,
                  stacks={p.player_id:p.stack for p in obs.players},
                  opponents=[p.player_id for p in obs.opponents],
                  history=[e.__dict__ if hasattr(e,'__dict__') else dict(type=e.type,seat=e.seat,action=e.action) for e in obs.history])
        self.upstream_calls += 1
        action = self.player.act(view)
        return translate(self, obs, action.type, action.amount)
