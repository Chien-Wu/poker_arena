from pathlib import Path
from types import SimpleNamespace as NS
from simulation.sdk import BaseBot
from utils.cards import equity
from utils.upstream import basic_environment, load_policy, translate


class Bot(BaseBot):
    def __init__(self, config=None, seed=0):
        super().__init__(config, seed)
        env = basic_environment()
        env['estimate_showdown_equity'] = lambda state, player, rng: equity(
            state.observation.hole_cards, state.observation.board,
            opponents=len(state.observation.opponents), samples=int(self.config['samples']), rng=rng)
        env['_pot_odds'] = lambda state, player: state.observation.legal_actions.call_amount / max(
            1, state.pot + state.observation.legal_actions.call_amount)
        self.policy = load_policy(Path(__file__).parent, env)['pot_odds_bot']

    def act(self, obs):
        legal = list(obs.legal_actions.types)
        if 'raise' in legal and obs.to_call == 0:
            legal[legal.index('raise')] = 'bet'
        if obs.hero.stack > 0 and (obs.hero.stack <= obs.to_call or 'raise' in obs.legal_actions.types):
            legal.append('all-in')
        state = NS(observation=obs, pot=obs.pot, street=obs.street,
                   rules=NS(big_blind=obs.big_blind), legal_actions=lambda: tuple(legal),
                   to_call=lambda player=None: obs.to_call)
        self.upstream_calls += 1
        action = self.policy(state, obs.hero_seat, self.rng)
        # Upstream engine's automatic aggressive amount is the minimum full
        # raise, capped by the stack. Translate to our explicit street raise-to.
        amount = obs.legal_actions.min_raise_to if action in ('bet', 'raise') else None
        return translate(self, obs, action, amount)
