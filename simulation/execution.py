"""Trusted in-process, timeout-isolated subprocess, and no-network Docker runners."""
from __future__ import annotations
from collections import deque
from contextlib import contextmanager
import copy
from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
import queue
import random
import signal
import subprocess
import sys
import threading
import time
import uuid
from .config import ExecutionConfig
from .contracts import Action
from .registry import Registry, ROOT

MAX_RESPONSE = 1_048_576


class BotFailure(RuntimeError):
    pass


class BotTimeout(BotFailure):
    pass


@contextmanager
def random_scope(owner):
    saved = random.getstate()
    random.setstate(owner.random_state)
    np = sys.modules.get("numpy")
    saved_np = None
    if np is not None:
        saved_np = np.random.get_state()
        if owner.numpy_state is None: np.random.seed(owner.seed % (2**32))
        else: np.random.set_state(owner.numpy_state)
    try:
        yield
    finally:
        owner.random_state = random.getstate()
        random.setstate(saved)
        if np is not None:
            owner.numpy_state = np.random.get_state()
            np.random.set_state(saved_np)


class InProcessRunner:
    def __init__(self, registry, entry, seed, config):
        self.seed = seed
        self.random_state = random.Random(seed).getstate()
        self.numpy_state = None
        with random_scope(self): self.bot = registry.load(entry.bot, entry.params, seed)
        self.telemetry = {}
        self.last_elapsed_ms = 0.0

    def call(self, method, data, timeout_ms):
        start = time.perf_counter()
        try:
            with random_scope(self): result = getattr(self.bot, method)(copy.deepcopy(data))
        except Exception as exc:
            raise BotFailure(f"{type(exc).__name__}: {exc}") from exc
        self.last_elapsed_ms = (time.perf_counter() - start) * 1000
        # In-process time checks detect overruns after return; they cannot preempt code.
        if self.last_elapsed_ms > timeout_ms: raise BotTimeout(f"{method} exceeded time budget")
        self.telemetry = {"upstream_calls": self.bot.upstream_calls, "adapter_repairs": self.bot.adapter_repairs}
        return result

    def close(self):
        try: self.bot.close()
        except Exception: pass


class ProcessRunner:
    def __init__(self, registry: Registry, entry, seed, config: ExecutionConfig):
        self._counter = 0
        self._queue = queue.Queue(maxsize=8)
        self._closing = threading.Event()
        self.stderr_tail = deque(maxlen=32)
        self.telemetry = {}
        self.last_elapsed_ms = 0.0
        self.docker_name = None
        self.config = config
        manifest = registry.manifest(entry.bot)
        bot_dir = registry.root / entry.bot
        command = [sys.executable, "-u", "-m", "simulation.worker", str(registry.root), entry.bot]
        if manifest["runtime"] == "command":
            command = [x.replace("{bot_dir}", str(bot_dir)) for x in manifest["command"]]
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT),
               "PYTHONHASHSEED": "0", "PYTHONUNBUFFERED": "1",
               "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        # Resource limits are applied by an exec launcher, never by preexec_fn
        # inside this threaded supervisor.
        if config.runner != "docker":
            command = [sys.executable, "-u", "-m", "simulation.launcher",
                       "--memory-mb", str(config.memory_mb), "--cpu-seconds", str(config.cpu_seconds),
                       "--", *command]
        if config.runner == "docker":
            self.docker_name = "poker-bot-" + uuid.uuid4().hex
            worker_command = ["python", "-u", "-m", "simulation.worker", "/bots", entry.bot]
            if manifest["runtime"] == "command":
                if not manifest.get("docker_command"):
                    raise BotFailure("Command bot must declare docker_command and provide that executable in the image")
                worker_command = [x.replace("{bot_dir}", f"/bots/{entry.bot}") for x in manifest["docker_command"]]
            command = ["docker", "run", "--rm", "--name", self.docker_name, "-i",
                       "--network", "none", "--read-only", "--cap-drop", "ALL",
                       "--security-opt", "no-new-privileges", "--pids-limit", "64",
                       "--memory", f"{config.memory_mb}m", "--memory-swap", f"{config.memory_mb}m", "--cpus", "1",
                       "--ulimit", f"cpu={config.cpu_seconds}:{config.cpu_seconds}",
                       "--ulimit", "nofile=256:256",
                       "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                       "--mount", f"type=bind,src={bot_dir},dst=/bots/{entry.bot},readonly",
                       "-e", "PYTHONHASHSEED=0", config.docker_image,
                       *worker_command]
            env = None
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, cwd=bot_dir, env=env,
                                            bufsize=0, start_new_session=True)
        except Exception as exc:
            raise BotFailure(f"Cannot launch {entry.bot}: {exc}") from exc
        self._threads = [threading.Thread(target=self._read_stdout, daemon=True),
                         threading.Thread(target=self._read_stderr, daemon=True)]
        for thread in self._threads: thread.start()
        try:
            self._request("initialize", {"seed": seed, "params": {**manifest.get("default_params", {}), **entry.params}},
                          config.startup_timeout_ms)
        except BaseException:
            self.close()
            raise

    def _enqueue(self, message):
        while not self._closing.is_set():
            try:
                self._queue.put(message, timeout=0.05)
                return
            except queue.Full:
                continue

    def _read_stdout(self):
        try:
            while True:
                line = self.process.stdout.readline(MAX_RESPONSE + 1)
                if not line: break
                if len(line) > MAX_RESPONSE:
                    self._enqueue(BotFailure("Oversized bot response")); return
                self._enqueue(line)
        except Exception as exc:
            self._enqueue(BotFailure(str(exc)))
        finally:
            self._enqueue(BotFailure("Bot process exited"))

    def _read_stderr(self):
        try:
            while line := self.process.stderr.readline(2048):
                self.stderr_tail.append(line.decode("utf-8", errors="replace"))
        except Exception: pass

    def _request(self, method, data, timeout_ms):
        self._counter += 1
        request = {"request_id": self._counter, "method": method, "data": data}
        start = time.perf_counter()
        payload = (json.dumps(request, allow_nan=False) + "\n").encode()
        if len(payload) > 8_388_608:
            raise BotFailure("Request exceeds the 8 MiB protocol limit")
        # A child that stops reading can fill its pipe. A bounded writer wait is
        # part of the same deadline as the response, not an unbounded write().
        sent = queue.Queue(maxsize=1)
        def write_request():
            try:
                self.process.stdin.write(payload)
                self.process.stdin.flush()
                sent.put(None)
            except (OSError, ValueError) as exc:
                sent.put(exc)
        threading.Thread(target=write_request, daemon=True).start()
        try:
            write_error = sent.get(timeout=timeout_ms / 1000)
        except queue.Empty as exc:
            self._kill()
            raise BotTimeout(f"{method} timed out writing request") from exc
        if write_error is not None:
            raise BotFailure("Bot stdin closed") from write_error
        remaining = timeout_ms / 1000 - (time.perf_counter() - start)
        try: message = self._queue.get(timeout=max(0, remaining))
        except queue.Empty as exc:
            self._kill()
            raise BotTimeout(f"{method} timed out after {timeout_ms} ms") from exc
        self.last_elapsed_ms = (time.perf_counter() - start) * 1000
        if isinstance(message, Exception): raise message
        try: response = json.loads(message)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BotFailure("Non-JSON stdout from bot") from exc
        if not isinstance(response, dict) or response.get("request_id") != self._counter:
            raise BotFailure("Mismatched response request_id")
        if "error" in response: raise BotFailure(response["error"])
        if method == "act" and "action" not in response:
            raise BotFailure("act response is missing action")
        if method != "act" and response.get("ok") is not True:
            raise BotFailure("Lifecycle response needs ok=true")
        telemetry = response.get("telemetry", {})
        if isinstance(telemetry, dict): self.telemetry = telemetry
        return response

    def call(self, method, data, timeout_ms):
        if is_dataclass(data): data = asdict(data)
        result = self._request(method, data, timeout_ms)
        if method == "act": return Action.from_dict(result["action"])
        return None

    def _kill(self):
        if self.docker_name:
            try: subprocess.run(["docker", "rm", "-f", self.docker_name], capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired): pass
        try:
            if os.name == "posix": os.killpg(self.process.pid, signal.SIGKILL)
            else: self.process.kill()
        except (ProcessLookupError, OSError): pass

    def close(self):
        if not hasattr(self, "process"): return
        if not self._closing.is_set() and self.process.poll() is None:
            try:
                self._request("close", {}, min(500, self.config.event_timeout_ms))
            except Exception:
                pass
        self._closing.set()
        self._kill()
        try: self.process.wait(timeout=3)
        except subprocess.TimeoutExpired: pass
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            try: stream.close()
            except Exception: pass


def make_runner(registry, entry, seed, config):
    if config.runner == "inprocess" and registry.manifest(entry.bot)["runtime"] == "python":
        return InProcessRunner(registry, entry, seed, config)
    return ProcessRunner(registry, entry, seed, config)
