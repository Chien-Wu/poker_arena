"""Atomic summaries and append-only journals."""
from __future__ import annotations
import csv
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path


def json_default(value):
    if is_dataclass(value): return asdict(value)
    if isinstance(value, Path): return str(value)
    raise TypeError(type(value).__name__)


def atomic_json(path: Path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, default=json_default, allow_nan=False) + "\n")
    temp.replace(path)


class Journal:
    def __init__(self, directory: Path | str | None):
        self.directory = Path(directory) if directory else None
        self.files = {}
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=False, mode=0o700)

    def write(self, name, record):
        if self.directory is None: return
        if name not in self.files:
            self.files[name] = (self.directory / f"{name}.jsonl").open("w", encoding="utf-8")
        self.files[name].write(json.dumps(record, default=json_default, separators=(",", ":"), allow_nan=False) + "\n")
        self.files[name].flush()

    def summary(self, name, value):
        if self.directory: atomic_json(self.directory / f"{name}.json", value)

    def csv(self, name, rows):
        if self.directory and rows:
            with (self.directory / f"{name}.csv").open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)

    def close(self):
        for file in self.files.values(): file.close()
