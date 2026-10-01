import random
import pytest
from utils.cards import evaluate,reference_best,equity,outcome_probabilities,DECK,validate_cards

@pytest.mark.parametrize('cards,expected',[
 ('As Ks Qs Js Ts',(8,14)),('As 2s 3s 4s 5s',(8,5)),
 ('As Ad Ah Ac 2s',(7,14,2)),('Qs Qd Qh Ks Kd',(6,12,13)),
 ('As Js 8s 5s 3s',(5,14,11,8,5,3)),('As 2d 3h 4c 5s',(4,5)),
 ('As Ad Ah Kc Qs',(3,14,13,12)),('As Ad Kh Kc Qs',(2,14,13,12)),
 ('As Ad Kh Qc Js',(1,14,13,12,11)),('As Kd Qh Jc 9s',(0,14,13,12,11,9)),
 ('As Ad Ah Kc Kd Kh 2s',(6,14,13)),('As Ad Ks Kd Qs Qd Jh',(2,14,13,12)),
])
def test_known_categories(cards,expected):assert evaluate(cards.split())==expected

@pytest.mark.parametrize('n',[5,6,7])
def test_differential_against_independent_reference(n):
    rng=random.Random(12345+n)
    for _ in range(5000):
        cards=rng.sample(DECK,n)
        assert evaluate(cards)==reference_best(cards)

def test_tied_board_equity_uses_fractional_pot_share():
    board=['As','Ks','Qs','Js','Ts']
    for opponents in (1,2,4,8):
        assert equity(['2c','3d'],board,opponents=opponents,samples=10,rng=random.Random(1))==pytest.approx(1/(opponents+1))
        assert outcome_probabilities(['2c','3d'],board,opponents=opponents,samples=10)==(0,0,1)

def test_equity_reproducible_and_bounds():
    a=equity(['As','Ad'],[],samples=100,rng=random.Random(9))
    b=equity(['As','Ad'],[],samples=100,rng=random.Random(9))
    assert a==b and 0<=a<=1

@pytest.mark.parametrize('cards',[['AS'],['SA'],['As','As'],['10s'],[1]])
def test_bad_cards(cards):
    with pytest.raises(ValueError):validate_cards(cards)

@pytest.mark.parametrize('samples',[0,-1,True,1.5])
def test_bad_simulation_count(samples):
    with pytest.raises(ValueError):equity(['As','Ad'],[],samples=samples)
    with pytest.raises(ValueError):outcome_probabilities(['As','Ad'],[],samples=samples)
