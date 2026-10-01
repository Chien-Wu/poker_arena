"""Create a future bot without changing the simulator or registry."""
from pathlib import Path
import json,re

ADAPTER='''from simulation.sdk import BaseBot
from .code.strategy import decide


class Bot(BaseBot):
    def act(self, observation):
        return decide(observation, self.config, self.rng)
'''
STRATEGY='''from simulation.contracts import Action, Observation
from random import Random


def decide(observation: Observation, config: dict, rng: Random) -> Action:
    """Example legal baseline. Replace this function with your strategy."""
    legal = observation.legal_actions
    if "check" in legal.types:
        return Action("check")
    if "call" in legal.types and legal.call_amount <= config.get("max_call", 20):
        return Action("call")
    return Action("fold")
'''

def create_bot(root:Path|str,bot_id:str,name:str|None=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',bot_id):raise ValueError('Unsafe bot id')
    directory=Path(root)/bot_id
    directory.mkdir(parents=True,exist_ok=False)
    (directory/'code').mkdir()
    (directory/'code'/'__init__.py').write_text('')
    (directory/'code'/'strategy.py').write_text(STRATEGY)
    (directory/'adapter.py').write_text(ADAPTER)
    manifest={'schema_version':1,'id':bot_id,'name':name or bot_id,'runtime':'python','entrypoint':'adapter:Bot',
              'capabilities':{'variant':'nlhe','min_players':2,'max_players':9},
              'default_params':{'max_call':20},'runtime_network':False,'competition_eligible':False,
              'provenance':{'kind':'user-template','note':'Eligibility requires the event organizer audit; not self-certified.'}}
    (directory/'bot.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return directory
