from pathlib import Path
from types import SimpleNamespace as NS
from simulation.sdk import BaseBot
from utils.cards import equity
from utils.upstream import basic_environment, load_policy, rich_cards, Rank, RichCard, position, translate

class Bot(BaseBot):
    def __init__(self, config=None, seed=0):
        super().__init__(config, seed)
        env = basic_environment()
        env.update(Card=RichCard, Rank=Rank, OpponentModel=lambda: NS(), OpponentStats=NS,
                   CFRStrategy=NS)
        env['estimate_equity'] = lambda hole, board, num_opponents=1, simulations=500: {
            'equity': equity([str(c) for c in hole], [str(c) for c in board],
                             opponents=num_opponents, samples=min(simulations,int(self.config['samples'])), rng=self.rng)}
        self.ns = load_policy(Path(__file__).parent, env)
        cls = type('ExtractedEthanPolicy', (), {name:self.ns[name] for name in ('__init__','decide','_preflop_decision','_postflop_decision')})
        self.player = cls(name='Ethan', style=self.config.get('style','balanced'), cfr_strategy=None)

    def act(self, obs):
        p = position(obs)
        cls = self.ns['Position']
        pos = cls.LATE if p in ('BTN','CO') else cls.BLINDS if p in ('SB','BB') else cls.EARLY if p=='UTG' else cls.MIDDLE
        self.upstream_calls += 1
        action, amount = self.player.decide(
            hole_cards=rich_cards(obs.hole_cards), community_cards=rich_cards(obs.board),
            pot=obs.pot, to_call=obs.to_call, stack=obs.hero.stack, position=pos,
            num_opponents=len(obs.opponents), street=obs.street,
            raise_count=sum(e.type=='action' and e.street==obs.street and e.action=='raise' for e in obs.history),
            opponent_name=None)
        return translate(self, obs, action.value, amount, amount_mode='pay_now')
