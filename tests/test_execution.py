import io
import json
import os
from pathlib import Path
import sys
import time
import pytest
from simulation.config import Entry,GameConfig,ExecutionConfig
from simulation.contracts import Action,ContractError
from simulation.engine import Hand
from simulation.execution import ProcessRunner,BotFailure,BotTimeout
from simulation.game import play_game
from simulation.registry import Registry,ROOT
from simulation.scaffold import create_bot


def candidate(tmp_path,body):
    create_bot(tmp_path,'candidate')
    (tmp_path/'candidate'/'adapter.py').write_text('from simulation.sdk import BaseBot\nfrom simulation.contracts import Action\nclass Bot(BaseBot):\n'+body)
    return Registry(tmp_path)


def test_subprocess_end_to_end_and_reproducibility():
    entries=[Entry('a','mybot1',{'equity_samples':10}),Entry('b','random_bot')]
    opts=dict(game=GameConfig(hands_per_game=5),execution=ExecutionConfig(failure_policy='abort'),seed=121,registry=Registry())
    a=play_game(entries,'repeatable',**opts);b=play_game(entries,'repeatable',**opts)
    assert a==b and a['hands']>0 and all(v['failures']==0 for v in a['stats'].values())


def test_timeout_kills_child(tmp_path):
    reg=candidate(tmp_path,'    def act(self,obs):\n        while True: pass\n')
    runner=ProcessRunner(reg,Entry('a','candidate'),1,ExecutionConfig())
    try:
        h=Hand(['a','b'],[1000]*2,button=0);start=time.monotonic()
        with pytest.raises(BotTimeout):runner.call('act',h.observation(0),80)
        assert time.monotonic()-start<3
    finally:runner.close()
    assert runner.process.poll() is not None


def test_prints_go_to_stderr_not_wire(tmp_path):
    reg=candidate(tmp_path,"    def act(self,obs):\n        print('diagnostic')\n        return Action('call')\n")
    runner=ProcessRunner(reg,Entry('a','candidate'),1,ExecutionConfig())
    try:
        h=Hand(['a','b'],[1000]*2,button=0)
        assert runner.call('act',h.observation(0),1000)==Action('call')
    finally:runner.close()


def test_missing_bot_never_counted_as_integration(tmp_path):
    with pytest.raises(ContractError):ProcessRunner(Registry(tmp_path),Entry('a','missing'),1,ExecutionConfig())


def test_constructor_failure_is_fatal(tmp_path):
    reg=candidate(tmp_path,"    def __init__(self,**kwargs): raise RuntimeError('no model')\n")
    with pytest.raises(BotFailure,match='no model'):ProcessRunner(reg,Entry('a','candidate'),1,ExecutionConfig())


def test_illegal_outputs_counted_and_safe_fallback(tmp_path):
    reg=candidate(tmp_path,"    def act(self,obs): return {'type':'raise','raise_to':-1}\n")
    create_bot(tmp_path,'other')
    result=play_game([Entry('a','candidate'),Entry('b','other')],'fault',game=GameConfig(hands_per_game=5),
                    execution=ExecutionConfig(max_failures_per_game=1),seed=1,registry=reg)
    assert result['stats']['a']['failures']==1 and 'a' in result['disabled']
    assert sum(result['stacks'].values())==4000


def test_subprocess_scrubs_credentials(tmp_path,monkeypatch):
    monkeypatch.setenv('SECRET_API_KEY','do-not-pass')
    reg=candidate(tmp_path,"    def act(self,obs):\n        import os\n        assert 'SECRET_API_KEY' not in os.environ\n        return Action('call')\n")
    runner=ProcessRunner(reg,Entry('a','candidate'),1,ExecutionConfig())
    try:
        h=Hand(['a','b'],[1000]*2,button=0);assert runner.call('act',h.observation(0),1000)==Action('call')
    finally:runner.close()


def test_pipe_write_stall_respects_deadline(tmp_path):
    create_bot(tmp_path,'sleeper')
    path=tmp_path/'sleeper';m=json.loads((path/'bot.json').read_text())
    m.update(runtime='command',command=[sys.executable,'-u',str(path/'wire.py')]);(path/'bot.json').write_text(json.dumps(m))
    (path/'wire.py').write_text("import sys,json,time\nx=json.loads(sys.stdin.readline())\nprint(json.dumps({'request_id':x['request_id'],'ok':True}),flush=True)\ntime.sleep(100)\n")
    runner=ProcessRunner(Registry(tmp_path),Entry('a','sleeper'),1,ExecutionConfig())
    try:
        start=time.monotonic()
        with pytest.raises(BotTimeout):runner.call('on_game_end',{'padding':'x'*1000000},100)
        assert time.monotonic()-start<3
    finally:runner.close()


def test_docker_flags_constructed_not_a_runtime_security_test(monkeypatch):
    import subprocess
    calls=[]
    def record(*args,**kwargs):calls.append((args,kwargs));raise OSError('test stop before launch')
    monkeypatch.setattr(subprocess,'Popen',record)
    with pytest.raises(BotFailure):ProcessRunner(Registry(),Entry('a','mybot1'),1,ExecutionConfig(runner='docker',require_no_network=True))
    command=calls[0][0][0]
    assert command[command.index('--network')+1]=='none'
    assert '--read-only' in command and '--cap-drop' in command
    assert '--pids-limit' in command and '--memory' in command
    assert command[command.index('--mount')+1].endswith('readonly')
    assert sum(x=='--mount' for x in command)==1


def test_ack_without_action_is_a_protocol_failure(tmp_path):
    create_bot(tmp_path,'ackonly')
    path=tmp_path/'ackonly';m=json.loads((path/'bot.json').read_text())
    m.update(runtime='command',command=[sys.executable,'-u',str(path/'wire.py')]);(path/'bot.json').write_text(json.dumps(m))
    (path/'wire.py').write_text("import sys,json\nfor line in sys.stdin:\n x=json.loads(line);print(json.dumps({'request_id':x['request_id'],'ok':True}),flush=True)\n")
    runner=ProcessRunner(Registry(tmp_path),Entry('a','ackonly'),1,ExecutionConfig())
    try:
        h=Hand(['a','b'],[1000]*2,button=0)
        with pytest.raises(BotFailure,match='missing action'):runner.call('act',h.observation(0),1000)
    finally:runner.close()


def test_normal_shutdown_calls_cleanup(tmp_path):
    marker=tmp_path/'closed'
    reg=candidate(tmp_path,"    def act(self,obs): return Action('call')\n    def close(self):\n        from pathlib import Path\n        Path("+repr(str(marker))+").write_text('closed')\n")
    runner=ProcessRunner(reg,Entry('a','candidate'),1,ExecutionConfig());runner.close()
    assert marker.read_text()=='closed'
