from utils.cards import DECK
from simulation.contracts import Action

def stacked_deck(hands,board,button=0):
    """Independent explicit deck construction for deterministic hand fixtures."""
    n=len(hands);order=[(button+i)%n for i in range(1,n+1)]
    selected=[c for hand in hands for c in hand]+list(board)
    assert len(set(selected))==len(selected)
    remaining=[c for c in DECK if c not in selected]
    deck=[hands[i][r] for r in range(2) for i in order]
    deck += [remaining.pop(0),*board[:3],remaining.pop(0),board[3],remaining.pop(0),board[4]]
    return deck+remaining

def check_call_to_end(hand):
    while not hand.terminal:
        kinds=hand.legal_actions().types
        hand.apply(Action('check' if 'check' in kinds else 'call'))
    return hand.result()
