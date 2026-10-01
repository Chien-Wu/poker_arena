"""Dependency-free Hold'em evaluator and uniform-card equity simulation.

Ranks compare lexicographically, higher is better. The fast 5–7-card evaluator
is tested against a separate five-card/combinations reference implementation.
"""
from __future__ import annotations
from collections import Counter
from itertools import combinations
import random

RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = tuple(r + s for s in SUITS for r in RANKS)


def validate_cards(cards, *, unique=True) -> tuple[str, ...]:
    cards = tuple(cards)
    if any(type(c) is not str or len(c) != 2 or c[0] not in RANKS or c[1] not in SUITS for c in cards):
        raise ValueError("Cards must be rank+suit strings, e.g. As, Td, 2c")
    if unique and len(set(cards)) != len(cards):
        raise ValueError("Duplicate cards")
    return cards


def straight_high(ranks) -> int:
    values = set(ranks)
    if 14 in values:
        values.add(1)
    for high in range(14, 4, -1):
        if all(high - offset in values for offset in range(5)):
            return high
    return 0


def evaluate(cards) -> tuple[int, ...]:
    """Rank any 5, 6 or 7 distinct canonical cards."""
    cards = tuple(cards)
    if not 5 <= len(cards) <= 7:
        raise ValueError("evaluate requires 5–7 cards")
    # Public callers validate once; this hot path deliberately avoids repeated validation.
    ranks = [RANKS.index(c[0]) + 2 for c in cards]
    counts = Counter(ranks)
    suits: dict[str, list[int]] = {}
    for c, r in zip(cards, ranks):
        suits.setdefault(c[1], []).append(r)
    flush = next((sorted(rs, reverse=True) for rs in suits.values() if len(rs) >= 5), None)
    if flush and (sf := straight_high(flush)):
        return (8, sf)
    quads = sorted((r for r, count in counts.items() if count == 4), reverse=True)
    if quads:
        return (7, quads[0], max(r for r in counts if r != quads[0]))
    trips = sorted((r for r, count in counts.items() if count >= 3), reverse=True)
    if trips:
        pairs = [r for r, count in counts.items() if count >= 2 and r != trips[0]]
        if pairs:
            return (6, trips[0], max(pairs))
    if flush:
        return (5, *flush[:5])
    if high := straight_high(ranks):
        return (4, high)
    if trips:
        return (3, trips[0], *sorted((r for r in counts if r != trips[0]), reverse=True)[:2])
    pairs = sorted((r for r, count in counts.items() if count >= 2), reverse=True)
    if len(pairs) >= 2:
        return (2, *pairs[:2], max(r for r in counts if r not in pairs[:2]))
    if pairs:
        return (1, pairs[0], *sorted((r for r in counts if r != pairs[0]), reverse=True)[:3])
    return (0, *sorted(counts, reverse=True)[:5])


def reference_five(cards) -> tuple[int, ...]:
    """Independent small reference used by tests, not the tournament hot path."""
    if len(cards) != 5:
        raise ValueError("Five cards required")
    values = sorted([RANKS.index(c[0]) + 2 for c in cards], reverse=True)
    groups = sorted(((values.count(v), v) for v in set(values)), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    unique = sorted(set(values))
    straight = 0
    if unique == [2, 3, 4, 5, 14]:
        straight = 5
    elif len(unique) == 5 and unique[-1] - unique[0] == 4:
        straight = unique[-1]
    pattern = [count for count, value in groups]
    ordered = tuple(value for count, value in groups)
    if flush and straight: return (8, straight)
    if pattern == [4, 1]: return (7, *ordered)
    if pattern == [3, 2]: return (6, *ordered)
    if flush: return (5, *values)
    if straight: return (4, straight)
    if pattern == [3, 1, 1]: return (3, *ordered)
    if pattern == [2, 2, 1]: return (2, *ordered)
    if pattern == [2, 1, 1, 1]: return (1, *ordered)
    return (0, *values)


def reference_best(cards) -> tuple[int, ...]:
    return max(reference_five(c) for c in combinations(cards, 5))


def equity(hole, board, opponents=1, samples=100, rng=None) -> float:
    """Expected showdown pot share, with uniform unknown cards; not a range solver."""
    if type(samples) is not int or samples < 1:
        raise ValueError("samples must be a positive integer")
    if type(opponents) is not int or not 1 <= opponents <= 8:
        raise ValueError("opponents must be 1–8")
    known = validate_cards(tuple(hole) + tuple(board))
    if len(hole) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("Invalid Hold'em cards")
    rng = rng or random.Random()
    remaining = [c for c in DECK if c not in known]
    share = 0.0
    need_board = 5 - len(board)
    for _ in range(samples):
        drawn = rng.sample(remaining, need_board + 2 * opponents)
        final_board = tuple(board) + tuple(drawn[:need_board])
        hero = evaluate(tuple(hole) + final_board)
        others = [evaluate(tuple(drawn[need_board + 2*i:need_board + 2*i + 2]) + final_board)
                  for i in range(opponents)]
        if hero >= max(others):
            share += 1.0 / (1 + sum(s == hero for s in others))
    return share / samples


def outcome_probabilities(hole, board, opponents=1, samples=100, rng=None):
    """Return strict win / lose / tie probabilities (not fractional pot share)."""
    if type(samples) is not int or samples < 1:
        raise ValueError("samples must be a positive integer")
    if type(opponents) is not int or not 1 <= opponents <= 8:
        raise ValueError("opponents must be 1–8")
    if len(hole) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("Invalid Hold'em cards")
    rng = rng or random.Random()
    known = validate_cards(tuple(hole) + tuple(board))
    remaining = [c for c in DECK if c not in known]
    wins = losses = ties = 0
    needed = 5 - len(board)
    for _ in range(samples):
        d = rng.sample(remaining, needed + 2*opponents)
        b = tuple(board) + tuple(d[:needed])
        own = evaluate(tuple(hole) + b)
        best = max(evaluate(tuple(d[needed+2*i:needed+2*i+2]) + b) for i in range(opponents))
        wins += own > best
        losses += own < best
        ties += own == best
    return wins / samples, losses / samples, ties / samples
