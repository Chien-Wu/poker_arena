"""JSON Lines Python bot worker. stdout is protocol-only, diagnostics go to stderr.

Run with `python -m simulation.worker /absolute/bots/root bot_id`.
A subprocess is a fault/time boundary, NOT a network/filesystem security sandbox.
"""
from __future__ import annotations
from contextlib import redirect_stdout
import json
from pathlib import Path
import random
import sys
import traceback
from .contracts import Action, Event, GameContext, Observation, HandResult
from .registry import Registry

MAX_BYTES = 8 * 1024 * 1024


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m simulation.worker BOT_ROOT BOT_ID")
    registry, bot_id = Registry(Path(sys.argv[1])), sys.argv[2]
    wire = sys.stdout
    bot = None
    try:
        while True:
            line = sys.stdin.buffer.readline(MAX_BYTES + 1)
            if not line: break
            if len(line) > MAX_BYTES: raise ValueError("Oversized input")
            request = json.loads(line)
            request_id = request.get("request_id")
            try:
                with redirect_stdout(sys.stderr):
                    method, data = request["method"], request.get("data", {})
                    if method == "initialize":
                        if bot is not None: raise ValueError("Already initialized")
                        random.seed(data["seed"])
                        bot = registry.load(bot_id, data.get("params", {}), data["seed"])
                        np = sys.modules.get("numpy")
                        if np is not None: np.random.seed(data["seed"] % (2**32))
                        response = {"ok": True}
                    elif bot is None:
                        raise ValueError("Worker has not been initialized")
                    elif method == "on_game_start":
                        bot.on_game_start(GameContext.from_dict(data)); response = {"ok": True}
                    elif method == "on_hand_start":
                        bot.on_hand_start(Observation.from_dict(data)); response = {"ok": True}
                    elif method == "on_event":
                        bot.on_event(Event.from_dict(data)); response = {"ok": True}
                    elif method == "act":
                        action = bot.act(Observation.from_dict(data))
                        if isinstance(action, dict): action = Action.from_dict(action)
                        if not isinstance(action, Action): raise TypeError("act must return Action")
                        response = {"action": action.to_dict(),
                                    "telemetry": {"upstream_calls": bot.upstream_calls,
                                                  "adapter_repairs": bot.adapter_repairs}}
                    elif method == "on_hand_end":
                        bot.on_hand_end(HandResult.from_dict(data)); response = {"ok": True}
                    elif method == "on_game_end":
                        bot.on_game_end(data); response = {"ok": True}
                    elif method == "close":
                        bot.close(); response = {"ok": True}
                    else:
                        raise ValueError(f"Unknown method: {method}")
                response["request_id"] = request_id
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                response = {"request_id": request_id, "error": f"{type(exc).__name__}: {exc}"}
            wire.write(json.dumps(response, allow_nan=False) + "\n")
            wire.flush()
            if request.get("method") == "close": break
    finally:
        if bot is not None:
            try:
                with redirect_stdout(sys.stderr): bot.close()
            except Exception: pass


if __name__ == "__main__": main()
