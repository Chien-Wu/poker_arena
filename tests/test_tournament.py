from dataclasses import replace
import json
import pytest
from simulation.config import Config,Entry,GameConfig,TournamentConfig,ExecutionConfig
from simulation.tournament import Tournament,placement_points,group_sizes,partition
from simulation.registry import Registry
from simulation.game import play_game
from simulation.replay import verify_file,verify_record

# A deterministic fake game tests tournament arithmetic ONLY, never bot coverage.
def fake_game(entries,game_id,**kwargs):
    ids=[e.id for e in entries];strength={x:int(x[1:])+1 for x in ids}
    return {'game_id':game_id,'purpose':kwargs.get('purpose','qualifier'),'seats':ids,'hands':1,
            'stacks':{x:1000+strength[x] for x in ids},'stats':{x:{} for x in ids}}

def tied_game(entries,game_id,**kwargs):
    x=fake_game(entries,game_id,**kwargs);x['stacks']={e.id:1000 for e in entries};return x

def config(n=10):
    return Config([Entry('p'+str(i),'random_bot') for i in range(n)],
                  GameConfig(hands_per_game=3),TournamentConfig(rounds=4,tiebreak_hands=1,tiebreak_attempts=1),
                  ExecutionConfig(runner='inprocess',failure_policy='abort'),123)

def test_two_scoring_layers_seats_regroup():
    t=Tournament(config(),game_function=fake_game);s=t.run()
    assert s['qualifier_games']==40 and len(s['rounds'])==4
    for round in s['rounds']:
        for g in round['groups']:
            assert len(g['games'])==5
            assert sum(g['game_points'].values())==75
            assert sorted(g['round_points'].values())==[1,2,3,4,5]
            for player in g['players']:
                assert sorted(game['seats'].index(player) for game in g['games'])==list(range(5))
    for previous,current in zip(s['rounds'],s['rounds'][1:]):
        expected=[p for tied in previous['ranking'] for p in tied]
        assert [p for g in current['groups'] for p in g['players']]==expected
    for row in s['leaderboard']:
        assert row['points']==sum(g['round_points'].get(row['player_id'],0) for r in s['rounds'] for g in r['groups'])

def test_tie_playoffs_bounded_and_not_fake_winner():
    c=config(2);c.tournament.rounds=1;c.tournament.group_size=2
    s=Tournament(c,game_function=tied_game).run()
    assert s['tiebreak_games']>0 and s['unresolved_ties']
    assert s['ranking']==[['p0','p1']]
    assert all(r['tied'] and r['rank']==1 and r['points']==1.5 for r in s['leaderboard'])

def test_tie_abort_policy():
    c=config(2);c.tournament.unresolved_ties='error'
    with pytest.raises(RuntimeError,match='Unresolved tie'):Tournament(c,game_function=tied_game).run()

def test_rank_point_tie_average():
    assert placement_points([['a'],['b','c'],['d']])=={'a':4,'b':2.5,'c':2.5,'d':1}

@pytest.mark.parametrize('n,target,sizes',[(10,5,[5,5]),(12,5,[4,4,4]),(11,5,[4,4,3]),(6,5,[3,3]),(2,5,[2])])
def test_balanced_group_sizes(n,target,sizes):assert group_sizes(n,target)==sizes

def test_no_singleton_group():
    with pytest.raises(ValueError):group_sizes(5,2)

def test_equal_group_requirement():
    c=config(11);c.tournament.require_equal_groups=True
    with pytest.raises(ValueError,match='Unequal'):Tournament(c)

def test_rotation_cycles_and_no_regroup():
    c=config(6);c.tournament.rounds=2;c.tournament.rotation_cycles=2;c.tournament.regroup=False
    s=Tournament(c,game_function=fake_game).run()
    assert s['qualifier_games']==24
    assert [g['players'] for g in s['rounds'][0]['groups']]==[g['players'] for g in s['rounds'][1]['groups']]

def test_real_tournament_replay_and_reproducibility(tmp_path):
    c=config(4);c.tournament.rounds=2;c.tournament.tiebreak_scope='final';c.tournament.group_size=4
    c.game.hands_per_game=6
    s=Tournament(c,output=tmp_path/'one').run()
    t=Tournament(c,output=tmp_path/'two').run()
    assert s==t and s['qualifier_games']==8
    assert verify_file(tmp_path/'one'/'private_hands.jsonl')==s['total_hands']
    records=[json.loads(x)['record'] for x in (tmp_path/'one'/'private_hands.jsonl').read_text().splitlines()]
    records[0]['final_stacks']=[0,0,0,0]
    # Recorded result schema is nested; corrupt the actual nested result below.
    records[0]['result']['final_stacks']=[0,0,0,0]
    with pytest.raises((ValueError,AssertionError)):verify_record(records[0])

def test_existing_result_folder_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):Tournament(config(2),output=tmp_path)
