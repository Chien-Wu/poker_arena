import json
from pathlib import Path
import pytest
from simulation.registry import Registry,ROOT
from simulation.config import Entry,GameConfig,ExecutionConfig
from simulation.game import play_game
from simulation.contracts import ContractError
from utils.io import Journal
from simulation.replay import verify_file

SOURCES=json.loads((ROOT/'sources.lock.json').read_text())['sources']

@pytest.mark.upstream
@pytest.mark.parametrize('bot',list(SOURCES))
def test_actual_selected_policy_runs_complete_hands(bot,tmp_path):
    receipt=ROOT/'bots'/bot/'code'/'upstream'/'receipt.json'
    if not receipt.exists():pytest.skip('Install explicit pinned source: python tools/fetch_upstreams.py --all')
    if bot=='up_pokerforbots' and not (ROOT/'bots'/bot/'code'/'handler').exists():pytest.skip('Build Go handler')
    reg=Registry();journal=Journal(tmp_path/'logs');total_calls=0
    try:
        for reverse in (False,True):
            entries=[Entry('source',bot,{'samples':16}),Entry('reference','random_bot')]
            if reverse:entries.reverse()
            result=play_game(entries,'adapter_'+bot+str(reverse),game=GameConfig(hands_per_game=12),
                             execution=ExecutionConfig(runner='subprocess',failure_policy='abort'),seed=130,
                             registry=reg,journal=journal)
            assert result['hands']>0 and result['stats']['source']['failures']==0
            assert result['stats']['source']['timeouts']==0
            total_calls+=result['stats']['source']['upstream_calls']
        assert total_calls>0  # no placeholder adapter or engine fallback counted as a policy call
    finally:journal.close()
    assert verify_file(tmp_path/'logs'/'private_hands.jsonl')>0

@pytest.mark.parametrize('bot',['up_fawz','up_gongsta','up_jeffelin','up_holdemlab'])
def test_hu_policy_not_silently_projected_to_multiway(bot):
    with pytest.raises(ContractError):Registry().check(bot,5)
