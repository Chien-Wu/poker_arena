import json
from dataclasses import FrozenInstanceError
import pytest
from simulation.contracts import Action, ContractError, Observation
from simulation.config import Config, Entry, override, ExecutionConfig
from simulation.engine import Hand
from simulation.sdk import BaseBot
from utils.upstream import translate

@pytest.mark.parametrize("value",[{},[],{"type":"jam"},{"type":"raise"},{"type":"call","raise_to":5},
 {"type":"raise","raise_to":True},{"type":"raise","raise_to":1.2},{"type":"raise","raise_to":0},
 {"type":"fold","amount":0},{"type":7}])
def test_bad_output_rejected(value):
    with pytest.raises((ContractError,TypeError)):Action.from_dict(value)

@pytest.mark.parametrize("a",[Action('fold'),Action('call'),Action('check'),Action('raise',100)])
def test_action_roundtrip(a):assert Action.from_dict(json.loads(json.dumps(a.to_dict())))==a

def test_frozen_contract():
    h=Hand(['a','b'],[1000,1000],button=0);o=h.observation(h.actor)
    with pytest.raises(FrozenInstanceError):o.pot=999
    with pytest.raises(FrozenInstanceError):o.hero.stack=999
    d=o.to_dict();d['players'][0]['stack']=888
    assert o.hero.stack!=888
    d=o.to_dict();d['schema_version']=2
    with pytest.raises(ContractError):Observation.from_dict(d)

@pytest.mark.parametrize('bad',[{'unknown':1},{'game':{'initial_stack':True}},{'tournament':{'rounds':0}},
 {'execution':{'require_no_network':True}},{'players':[{'id':'a','bot':'../escape'},{'id':'b','bot':'random_bot'}]}])
def test_config_rejects(bad):
    d=Config([Entry('a','random_bot'),Entry('b','random_bot')]).to_dict();d.update(bad)
    with pytest.raises((ValueError,TypeError)):Config.from_dict(d)

def test_dotted_overrides_and_nonmutation():
    c=Config([Entry('a','mybot1'),Entry('b','random_bot')])
    d=override(c,['players.0.params.samples=10','game.hands_per_game=50','tournament.regroup=false'])
    assert d.players[0].params['samples']==10 and d.game.hands_per_game==50 and not d.tournament.regroup
    assert c.players[0].params=={}

def test_seed_resolution_is_private_configuration():
    c=Config([Entry('a','random_bot'),Entry('b','random_bot')]);assert c.seed is None
    assert c.resolved().seed!=c.resolved().seed
    c.seed=123;assert c.resolved().seed==123

def test_amount_translation_exact_semantics():
    h=Hand(['a','b'],[1000,1000],button=0);o=h.observation(0);b=BaseBot()
    assert translate(b,o,'raise',70,amount_mode='raise_to')==Action('raise',70)
    assert translate(b,o,'raise',60,amount_mode='pay_now')==Action('raise',70)
    assert translate(b,o,'raise',50,amount_mode='raise_by')==Action('raise',70)
    assert b.adapter_repairs==0
    assert translate(b,o,'raise',1)==Action('raise',40)
    assert b.adapter_repairs==1
    with pytest.raises(ValueError):translate(b,o,'unexpected',0)

def test_no_network_mode_cannot_silently_downgrade():
    for runner in ('inprocess','subprocess'):
        with pytest.raises(ContractError):ExecutionConfig(runner=runner,require_no_network=True).validate()
    ExecutionConfig(runner='docker',require_no_network=True).validate()


@pytest.mark.parametrize("value", [True, "false"])
def test_network_required_bot_is_not_admitted(tmp_path, value):
    from simulation.scaffold import create_bot
    from simulation.registry import Registry
    directory = create_bot(tmp_path, "network_bot")
    path = directory / "bot.json"
    manifest = json.loads(path.read_text())
    manifest["runtime_network"] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ContractError):
        Registry(tmp_path).manifest("network_bot")
