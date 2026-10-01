"""Bot discovery by manifest, not by hard-coded imports."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
from .contracts import ContractError

ROOT = Path(__file__).resolve().parents[1]


class Registry:
    def __init__(self, root: Path | str = ROOT / "bots"):
        self.root = Path(root).resolve()

    def manifest(self, bot_id: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", bot_id): raise ContractError("Unsafe bot id")
        path = self.root / bot_id / "bot.json"
        if not path.is_file(): raise ContractError(f"Unknown bot {bot_id!r}: {path}")
        m = json.loads(path.read_text())
        if m.get("schema_version") != 1 or m.get("id") != bot_id:
            raise ContractError(f"Invalid manifest identity/version in {path}")
        if m.get("runtime") not in {"python", "command"}: raise ContractError("Unknown bot runtime")
        if m.get("runtime") == "python" and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*:[A-Za-z_][A-Za-z0-9_]*", m.get("entrypoint", "")):
            raise ContractError("Python entrypoint must look like adapter:Bot")
        if m.get("runtime") == "command" and (not isinstance(m.get("command"), list) or not m["command"]):
            raise ContractError("command must be a non-empty argument array, never a shell string")
        if type(m.get("runtime_network", False)) is not bool:
            raise ContractError("runtime_network must be a boolean")
        if m.get("runtime_network", False):
            raise ContractError("Runtime-network decision bots are not admitted by this arena profile")
        cap = m.get("capabilities", {})
        if cap.get("variant") != "nlhe" or not 2 <= cap.get("min_players", 0) <= cap.get("max_players", 0) <= 9:
            raise ContractError("This engine accepts explicit 2–9 player NLHE capabilities")
        return m

    def list(self):
        return [self.manifest(path.parent.name) for path in sorted(self.root.glob("*/bot.json"))]

    def check(self, bot_id, players):
        m = self.manifest(bot_id)
        c = m["capabilities"]
        if not c["min_players"] <= players <= c["max_players"]:
            raise ContractError(f"{bot_id} supports {c['min_players']}–{c['max_players']} seats, not {players}")
        # Knockouts and tie-breaks can reduce a table to heads-up.
        if c["min_players"] != 2:
            raise ContractError(f"{bot_id} must support heads-up tie-breaks and knockouts")
        return m

    def load(self, bot_id, config, seed):
        m = self.manifest(bot_id)
        if m["runtime"] != "python": raise ContractError("Command bots need a process runner")
        path = self.root / bot_id
        module_name, class_name = m["entrypoint"].split(":")
        namespace = "arena_plugin_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
        if namespace not in sys.modules:
            package = types.ModuleType(namespace)
            package.__path__ = [str(path)]
            sys.modules[namespace] = package
        full_name = namespace + "." + module_name
        spec = importlib.util.spec_from_file_location(full_name, path / f"{module_name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)
        params = {**m.get("default_params", {}), **config}
        return getattr(module, class_name)(config=params, seed=seed)

    def fingerprint(self, bot_id):
        path = self.root / bot_id
        h = hashlib.sha256()
        for file in sorted(path.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix not in {".pyc", ".exe"}:
                h.update(str(file.relative_to(path)).encode()); h.update(file.read_bytes())
        return h.hexdigest()
