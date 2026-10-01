"""Independent, stable namespaces for deals, seat schedules and policy randomness."""
import hashlib
import json


def derive_seed(master: int, *parts) -> int:
    payload = json.dumps([master, *parts], separators=(",", ":"), ensure_ascii=True).encode()
    return int.from_bytes(hashlib.blake2b(payload, digest_size=16).digest(), "big")
