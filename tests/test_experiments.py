import json
import pytest
from simulation.config import Config,Entry,GameConfig,TournamentConfig,ExecutionConfig
from simulation.experiments import repeat,sweep
from simulation.scaffold import create_bot
from simulation.registry import Registry
from simulation.engine import Hand
from simulation.contracts import Action

def quick():
    return Config([Entry('a','random_bot'),Entry('b','calling_bot')],GameConfig(hands_per_game=2),
                  TournamentConfig(rounds=1,group_size=2,tiebreak_hands=1,tiebreak_attempts=1,tiebreak_scope='final'),
                  ExecutionConfig(runner='inprocess',failure_policy='abort'),999)

def test_repeat_resume_and_seed_stream(tmp_path):
    path=tmp_path/'experiment';a=repeat(quick(),2,path);b=repeat(quick(),2,path,resume=True)
    assert a==b and a['completed_iterations']==2
    seeds=[json.loads((path/f'iteration_{i:04d}'/'summary.json').read_text())['seed'] for i in (1,2)]
    assert len(set(seeds))==2
    changed=quick();changed.game.hands_per_game=3
    with pytest.raises(ValueError,match='identical'):repeat(changed,2,path,resume=True)

def test_resume_preserves_incomplete_run(tmp_path):
    path=tmp_path/'experiment';repeat(quick(),2,path)
    (path/'iteration_0002'/'summary.json').unlink()
    repeat(quick(),2,path,resume=True)
    assert (path/'iteration_0002.interrupted.1').exists()
    assert (path/'iteration_0002'/'summary.json').exists()

def test_cartesian_sweep(tmp_path):
    result=sweep(quick(),{'game.hands_per_game':[1,2],'game.ante':[0,1]},1,tmp_path/'sweep')
    assert len(result)==4
    assert len({x['master_seed'] for x in result})==1

def test_new_bot_format_requires_no_registry_code_changes(tmp_path):
    create_bot(tmp_path,'new_policy')
    reg=Registry(tmp_path);m=reg.manifest('new_policy')
    assert m['entrypoint']=='adapter:Bot'
    b=reg.load('new_policy',{},42)
    h=Hand(['a','b'],[1000]*2,button=0);o=h.observation(h.actor);a=b.act(o);o.legal_actions.validate(a)
    assert isinstance(a,Action)
    with pytest.raises(FileExistsError):create_bot(tmp_path,'new_policy')
    with pytest.raises(ValueError):create_bot(tmp_path,'../escape')
