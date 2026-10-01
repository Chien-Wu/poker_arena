#!/usr/bin/env python3
"""Exhaustive five-card category verification; no external evaluator dependency."""
import argparse
from collections import Counter
import itertools
from math import comb
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils.cards import DECK,evaluate
from utils.io import atomic_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path)
    args=parser.parse_args();start=time.perf_counter()
    observed=Counter(evaluate(hand)[0] for hand in itertools.combinations(DECK,5))
    # Exact combinatorial category counts, including wheel straight flushes.
    expected={
        8: 4 * 10,                              # straight flush
        7: 13 * 12 * 4,                         # quads, kicker
        6: 13 * comb(4,3) * 12 * comb(4,2),     # full house
        5: 4 * (comb(13,5) - 10),               # flush, not straight flush
        4: 10 * (4**5 - 4),                     # straight, not flush
        3: 13 * comb(4,3) * comb(12,2) * 4**2,  # trips, distinct kickers
        2: comb(13,2) * comb(4,2)**2 * 11 * 4,  # two pair, kicker
        1: 13 * comb(4,2) * comb(12,3) * 4**3,  # one pair
        0: (comb(13,5) - 10) * (4**5 - 4),      # high card
    }
    assert dict(observed)==expected,(observed,expected)
    report={'hands':sum(observed.values()),'category_counts':dict(sorted(observed.items())),
            'status':'passed','elapsed_seconds':round(time.perf_counter()-start,3)}
    if args.out:atomic_json(args.out,report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
