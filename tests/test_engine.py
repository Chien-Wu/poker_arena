from dataclasses import asdict
import copy,json,random
import pytest
from simulation.engine import Hand
from simulation.contracts import Action,ContractError,Observation
from utils.cards import DECK
from tests.helpers import stacked_deck,check_call_to_end


def test_heads_up_button_is_small_blind_and_acts_first_preflop():
    h=Hand(['a','b'],[1000,1000],button=1)
    assert (h.sb_seat,h.bb_seat,h.actor)==(1,0,1)
    h.apply(Action('call'))
    assert h.actor==0 and 'check' in h.legal_actions().types and 'raise' in h.legal_actions().types
    h.apply(Action('check'))
    assert h.street=='flop' and h.actor==0 and len(h.board)==3

@pytest.mark.parametrize('n',range(3,10))
def test_multiway_blinds_and_order(n):
    button=n-2
    h=Hand([str(i) for i in range(n)],[1000]*n,button=button)
    assert (h.sb_seat,h.bb_seat,h.actor)==((button+1)%n,(button+2)%n,(button+3)%n)
    assert h.legal_actions().to_call==20
    assert h.legal_actions().min_raise_to==40

def test_fold_refunds_uncalled_blind_and_does_not_reveal_cards():
    h=Hand(['a','b'],[1000]*2,button=0)
    h.apply(Action('fold'))
    r=h.result()
    assert r.final_stacks==(990,1010)
    assert not r.shown_cards
    assert any(e.type=='refund' and e.paid==10 for e in h.history)
    assert sum(p['amount'] for p in r.pots)==20

def test_big_blind_gets_option_after_calls():
    h=Hand(['a','b','c'],[1000]*3,button=0)
    h.apply(Action('call'));h.apply(Action('call'))
    assert h.actor==2 and h.legal_actions().to_call==0
    assert 'raise' in h.legal_actions().types
    h.apply(Action('check'))
    assert h.street=='flop' and h.actor==1 and h.pot==60

def test_raise_to_and_minimum_raise_increment():
    h=Hand(list('abcd'),[1000]*4,button=0)
    h.apply(Action('raise',100))
    assert h.history[-1].paid==100
    assert h.legal_actions().min_raise_to==180
    h.apply(Action('call'))
    assert h.actor==1
    h.apply(Action('raise',180))
    assert h.history[-1].paid==170
    assert h.legal_actions().min_raise_to==260

def test_illegal_action_is_atomic():
    h=Hand(list('abc'),[1000]*3,button=0)
    before=copy.deepcopy(h.__dict__)
    with pytest.raises(ContractError):h.apply(Action('raise',39))
    assert h.__dict__==before
    with pytest.raises(ContractError):h.apply(Action('check'))
    assert h.__dict__==before

def test_short_all_in_does_not_reopen():
    h=Hand(list('abc'),[1000,130,1000],button=0)
    h.apply(Action('raise',100))
    assert h.legal_actions().full_min_raise_to==180
    assert h.legal_actions().min_raise_to==h.legal_actions().max_raise_to==130
    assert h.legal_actions().short_all_in_only
    h.apply(Action('raise',130));h.apply(Action('call'))
    assert h.actor==0 and h.legal_actions().to_call==30
    assert 'raise' not in h.legal_actions().types
    h.apply(Action('call'))
    assert h.street=='flop'

def test_cumulative_short_all_ins_reopen_by_player():
    h=Hand(list('abcd'),[1000,150,200,1000],button=0)
    h.apply(Action('raise',100));h.apply(Action('call'))
    h.apply(Action('raise',150));h.apply(Action('raise',200))
    assert h.actor==3 and h.last_full_raise==80
    assert h.legal_actions().min_raise_to==280
    h.apply(Action('call'))
    assert h.actor==0 and 'raise' in h.legal_actions().types

def test_recent_caller_does_not_get_same_reopening_as_earlier_caller():
    h=Hand(list('abcde'),[150,1000,200,1000,1000],button=0)
    h.apply(Action('raise',100));h.apply(Action('call'))
    h.apply(Action('raise',150));h.apply(Action('call'));h.apply(Action('raise',200))
    assert h.actor==3 and 'raise' in h.legal_actions().types
    h.apply(Action('call'));h.apply(Action('call'))
    assert h.actor==1 and h.legal_actions().to_call==50
    assert 'raise' not in h.legal_actions().types

def test_short_call_sidepots_and_uncalled_refund():
    deck=stacked_deck([['As','Ad'],['Ks','Kd'],['Qs','Qd']],['2c','3d','7h','8s','Tc'],button=2)
    h=Hand(list('abc'),[100,200,300],button=2,deck=deck)
    assert h.actor==2
    h.apply(Action('raise',300));h.apply(Action('call'));h.apply(Action('call'))
    assert h.terminal and h.result().final_stacks==(300,200,100)
    assert [p['amount'] for p in h.result().pots]==[300,200]
    assert h.result().pots[0]['winners']==[0]
    assert h.result().pots[1]['winners']==[1]
    assert any(e.type=='refund' and e.paid==100 for e in h.history)

def test_no_raising_into_a_dry_sidepot():
    h=Hand(list('abc'),[100,200,300],button=0)
    h.apply(Action('raise',100));h.apply(Action('raise',200))
    assert h.actor==2 and h.legal_actions().types==('fold','call')

def test_folded_money_remains_but_folded_hands_cannot_win():
    deck=stacked_deck([['As','Ad'],['Ks','Kd'],['Qs','Qd'],['Js','Jd']],['2c','3d','7h','8s','Tc'])
    h=Hand(list('abcd'),[100,200,200,200],button=0,deck=deck)
    h.apply(Action('call'));h.apply(Action('raise',100));h.apply(Action('raise',200));h.apply(Action('call'));h.apply(Action('fold'))
    assert h.terminal and h.result().final_stacks==(320,200,0,180)
    assert [p['amount'] for p in h.result().pots]==[320,200]
    assert 3 not in dict(h.result().shown_cards)

def test_odd_chip_goes_clockwise_after_button():
    deck=stacked_deck([['As','Kc'],['Ah','Kd'],['Qs','Jd']],['Ac','7c','8d','4s','2h'])
    h=Hand(list('abc'),[20]*3,button=0,small_blind=1,big_blind=1,deck=deck)
    r=check_call_to_end(h)
    assert r.final_stacks==(20,21,19)
    assert r.pots[0]['awards']=={'1':2,'0':1}

def test_merge_identical_eligible_tiers_before_awarding_odd_chips():
    deck=stacked_deck([['As','Kc'],['Ah','Kd'],['Qs','Jd'],['3s','5d'],['9s','Td']],['Ac','7c','8d','4s','2h'])
    h=Hand(list('abcde'),[100]*5,button=0,small_blind=1,big_blind=1,ante=1,deck=deck)
    h.apply(Action('fold'));h.apply(Action('fold'))
    r=check_call_to_end(h)
    # Raw contribution tiers are 5 and 3, but BOTH have the same live eligible
    # seats. Separate rounding would wrongly award 5/3 instead of 4/4.
    assert r.final_stacks==(102,102,98,99,99)
    assert len(r.pots)==1 and r.pots[0]['amount']==8
    assert r.pots[0]['awards']=={'1':4,'0':4}

def test_all_in_blind_auto_runout():
    deck=stacked_deck([['As','Ad'],['Ks','Kd']],['2c','3d','7h','8s','Tc'])
    h=Hand(list('ab'),[1,100],button=0,deck=deck)
    assert h.terminal and h.result().final_stacks==(2,99)
    assert not h.actions and len(h.board)==5

def test_partial_big_blind_still_sets_nominal_bring_in_multiway():
    h=Hand(list('abc'),[1000,1000,5],button=0)
    assert h.actor==0 and h.legal_actions().to_call==20
    assert h.legal_actions().min_raise_to==40
    h.apply(Action('call'));h.apply(Action('call'))
    assert h.street=='flop' and h.pot==45
    assert [p.amount for p in h.pot_views()]==[15,30]

def test_busted_seats_are_skipped_and_private_cards_not_dealt():
    h=Hand(list('abcde'),[100,0,200,0,300],button=2)
    assert h.sb_seat==4 and h.bb_seat==0 and h.actor==2
    with pytest.raises(ValueError):h.observation(1)
    assert h.observation(2).players[1].status=='out'

def test_observation_round_trip_and_hidden_information_boundary():
    h=Hand(list('abc'),[1000]*3,button=0,seed=123)
    o=h.observation(0);raw=o.to_dict()
    rebuilt=Observation.from_dict(json.loads(json.dumps(raw)))
    assert o==rebuilt
    text=json.dumps(raw)
    assert 'deck' not in text and 'seed' not in text
    assert tuple(raw['hole_cards'])==tuple(h._hole_cards[0])
    for seat in (1,2):
        for c in h._hole_cards[seat]:assert c not in text
    assert not h.observation(1).legal_actions.types

def test_check_then_incomplete_open_does_not_reopen_under_full_bet_profile():
    # Explicit full-bet profile: a previously checked player needs to face at
    # least a full opening increment before it can raise again.
    h=Hand(list('abcd'),[1000,1000,30,1000],button=0)
    for _ in range(4):h.apply(Action('call' if h.legal_actions().to_call else 'check'))
    assert h.street=='flop' and h.actor==1
    h.apply(Action('check'));h.apply(Action('raise',10));h.apply(Action('call'));h.apply(Action('call'))
    assert h.actor==1 and 'raise' not in h.legal_actions().types

@pytest.mark.parametrize('seed',range(120))
def test_randomized_games_conserve_chips_and_terminate(seed):
    rng=random.Random(seed)
    for n in range(2,10):
        stacks=[rng.randint(1,1000) for _ in range(n)]
        h=Hand([str(i) for i in range(n)],stacks,button=seed%n,ante=seed%7,seed=seed*10+n)
        count=0
        while not h.terminal:
            l=h.legal_actions();kind=rng.choice(l.types)
            a=Action(kind,rng.choice([l.min_raise_to,l.max_raise_to]) if kind=='raise' else None)
            h.apply(a);h.assert_invariants();count+=1
            assert count<1000
        assert sum(h.stacks)==sum(stacks)
