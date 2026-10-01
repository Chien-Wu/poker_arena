"""Load pinned, source-extracted upstream policies without importing their GUIs.

This is a dependency boundary, NOT a security sandbox. Python code is code.
Only tools/fetch_upstreams.py performs network I/O; match workers never fetch.
"""
from __future__ import annotations
import ast
from dataclasses import dataclass
from enum import Enum, IntEnum
import hashlib
import json
from pathlib import Path
import random
import sys
import types
from types import SimpleNamespace
from typing import Any

from simulation.contracts import Action, Observation
from utils.cards import DECK, RANKS, SUITS, equity, evaluate, outcome_probabilities


class MissingUpstream(RuntimeError):
    pass


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def extract_source(text: str, selectors: list[str]) -> str:
    """Select whole declarations or Class.method; keep decision bodies intact.

    Imports at module level are intentionally excluded. The adapter supplies the
    documented dependencies. Nested imports remain in the original function.
    """
    tree = ast.parse(text)
    wanted = set(selectors)
    found = set()
    selected = []
    for node in tree.body:
        names = []
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        matching = wanted.intersection(names)
        if matching:
            found.update(matching)
            selected.append(node)
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    key = node.name + "." + member.name
                    if key in wanted:
                        if member.decorator_list:
                            raise ValueError(f"Select the whole class for decorated method {key}")
                        selected.append(member)
                        found.add(key)
    if found != wanted:
        raise ValueError(f"Missing upstream declarations: {sorted(wanted - found)}")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    result = ast.Module(body=[future, *selected], type_ignores=[])
    return ast.unparse(ast.fix_missing_locations(result)) + "\n"


def load_policy(bot_dir: str | Path, environment: dict[str, Any]) -> dict[str, Any]:
    path = Path(bot_dir) / "code" / "upstream"
    receipt_path = path / "receipt.json"
    if not receipt_path.exists():
        raise MissingUpstream(
            f"{Path(bot_dir).name}: upstream source is not installed. "
            "Run python tools/fetch_upstreams.py --all before starting a match. "
            "No substitute policy will be used."
        )
    receipt = json.loads(receipt_path.read_text())
    files = receipt.get("policies", [])
    if not files:
        raise MissingUpstream("Empty upstream extraction receipt")
    module_name = "arena_upstream_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:20]
    mod = types.ModuleType(module_name)
    mod.__dict__.update(environment)
    sys.modules[module_name] = mod
    for item in files:
        file = path / item["file"]
        code = file.read_bytes()
        if hashlib.sha256(code).hexdigest() != item["sha256"]:
            raise MissingUpstream(f"Modified upstream extract: {file}. Re-run the explicit installer.")
        exec(compile(code, str(file), "exec"), mod.__dict__)
    return mod.__dict__


def basic_environment() -> dict[str, Any]:
    from collections import defaultdict
    from typing import Dict, List, Optional, Set, Tuple
    return dict(random=random, Enum=Enum, IntEnum=IntEnum, dataclass=dataclass,
                defaultdict=defaultdict, SimpleNamespace=SimpleNamespace,
                List=List, Dict=Dict, Tuple=Tuple, Optional=Optional, Set=Set)


def numpy_environment() -> dict[str, Any]:
    try:
        import numpy as np
    except ImportError as exc:
        raise MissingUpstream("This upstream policy requires numpy; install requirements-upstreams.txt") from exc
    return {**basic_environment(), "np": np}


def passive(obs: Observation) -> Action:
    if "check" in obs.legal_actions.types: return Action("check")
    if "call" in obs.legal_actions.types: return Action("call")
    return Action("fold")


def translate(owner, obs: Observation, kind: str, amount=None, *, amount_mode="raise_to") -> Action:
    """Explicit, metered legalization of a legacy strategy's requested action.

    raise_to = total street commitment; pay_now = new chips INCLUDING the call;
    raise_by = increment ABOVE the current table wager. Every correction is
    counted; the core engine itself never silently clips an action.
    """
    aliases = {"f": "fold", "k": "check", "c": "call", "b": "raise", "bet": "raise",
               "allin": "all_in", "all-in": "all_in"}
    kind = aliases.get(kind, kind)
    legal = obs.legal_actions
    if kind == "all_in":
        if obs.hero.stack <= legal.to_call:
            return Action("call")
        kind, amount, amount_mode = "raise", obs.hero.street_bet + obs.hero.stack, "raise_to"
    if kind == "call" and "check" in legal.types:
        return Action("check")  # Many protocols deliberately merge check and call.
    if kind == "raise":
        if "raise" not in legal.types:
            owner.adapter_repairs += 1
            return passive(obs)
        if amount is None:
            raise ValueError("An upstream raise must have a size or a documented fixed-size conversion")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("Non-numeric upstream bet amount")
        import math
        if not math.isfinite(amount): raise ValueError("Non-finite upstream amount")
        target = int(round(amount))
        if amount_mode == "pay_now": target += obs.hero.street_bet
        elif amount_mode == "raise_by": target += obs.hero.street_bet + legal.to_call
        elif amount_mode != "raise_to": raise ValueError("Unknown upstream amount mode")
        bounded = min(legal.max_raise_to, max(legal.min_raise_to, target))
        if bounded != target or amount != round(amount): owner.adapter_repairs += 1
        return Action("raise", bounded)
    if kind in legal.types:
        return Action(kind)
    if kind not in {"fold", "check", "call"}:
        raise ValueError(f"Unknown upstream action {kind!r}")
    owner.adapter_repairs += 1
    return passive(obs)


def position(obs: Observation) -> str:
    if obs.hero_seat == obs.button_seat: return "BTN"
    if obs.hero_seat == obs.small_blind_seat: return "SB"
    if obs.hero_seat == obs.big_blind_seat: return "BB"
    seats = [p.seat for p in obs.players if p.status != "out"]
    order = sorted(seats, key=lambda s: (s - obs.big_blind_seat - 1) % len(obs.players))
    idx = order.index(obs.hero_seat)
    return "UTG" if idx == 0 else "CO" if idx == len(order) - 4 else "MP"


Rank = IntEnum("Rank", {name: value for name, value in zip(
    ["TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "JACK", "QUEEN", "KING", "ACE"], range(2, 15))})


@dataclass(frozen=True)
class RichCard:
    rank: Rank
    suit: str
    def __str__(self): return RANKS[int(self.rank) - 2] + self.suit


def rich_cards(cards): return [RichCard(Rank(RANKS.index(c[0]) + 2), c[1]) for c in cards]


def install_module(name: str, **values):
    """Provide a small dependency facade for an original nested import."""
    parts = name.split(".")
    for k in range(1, len(parts) + 1):
        key = ".".join(parts[:k])
        if key not in sys.modules:
            mod = types.ModuleType(key); mod.__path__ = []
            sys.modules[key] = mod
        if k > 1: setattr(sys.modules[".".join(parts[:k-1])], parts[k-1], sys.modules[key])
    sys.modules[name].__dict__.update(values)
