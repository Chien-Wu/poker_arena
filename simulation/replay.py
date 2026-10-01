"""Re-execute every logged legal action and verify exact settlement."""
from dataclasses import asdict
import json
from pathlib import Path
from .contracts import Action
from .engine import Hand


def verify_record(record):
    if record.get("rules_profile") != "nlhe-moving-button-v1": raise ValueError("Unsupported rules profile")
    hand = Hand(record["player_ids"], record["starting_stacks"], button=record["button"],
                small_blind=record["small_blind"], big_blind=record["big_blind"], ante=record["ante"],
                deck=record["deck"], game_id=record["game_id"], hand_number=record["hand_number"])
    for item in record["actions"]:
        if hand.actor != item["seat"]: raise AssertionError("Replay actor mismatch")
        hand.apply(Action.from_dict(item["action"]))
    if not hand.terminal: raise AssertionError("Replay ended before settlement")
    normalized = json.loads(json.dumps(asdict(hand.result())))
    if normalized != record["result"]: raise AssertionError("Replay result/history mismatch")
    return hand


def verify_file(path):
    count = 0
    with Path(path).open() as file:
        for line in file:
            data = json.loads(line)
            verify_record(data.get("record", data))
            count += 1
    return count
