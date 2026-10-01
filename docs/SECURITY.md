# Execution and security boundary

## Three runners, three different claims

| Runner | What it does | What it does not do |
|---|---|---|
| `inprocess` | Fast, sequential trusted-code execution; per-bot RNG state; detects time overruns after return | Cannot preempt infinite loops, isolate globals/files, deny networking, or protect engine memory |
| `subprocess` | Separate worker per competitor, minimal environment, request/response validation, kill-on-timeout, Linux address-space/CPU/file-descriptor limits | Does not deny networking or prevent access to the host filesystem or other same-user processes |
| `docker` | No network, read-only root/bot mount, reduced privileges, limited PIDs/memory/CPU, only the selected bot directory and SDK exposed | Not a formal proof against kernel/container escapes, collusion, or every malicious resource attack |

Only Docker is accepted when `execution.require_no_network=true`. The simulator refuses to silently fall back to a network-capable runner. None of the supplied policies uses a runtime LLM or remote decision API.

**Validation status:** subprocess error/timeout/pipe-stall behavior is tested. Docker argument construction and strict configuration gating are tested; actual Docker image build, network-denial behavior, cgroups, and filesystem isolation were not executed in the delivery environment. Test them on the deployment host before receiving untrusted submissions.

## Build and use the no-network profile

Native and Python-policy SDK image:

```bash
docker build -f docker/Dockerfile -t poker-arena-bot:local .
python -m simulation run -c configs/no_network.json --out results/isolated
```

For all twelve repository adapters, first acquire sources and dependencies outside the runtime. Build the multi-stage image that also compiles the Go reference handler:

```bash
python tools/fetch_upstreams.py --all
docker build -f docker/Dockerfile.all -t poker-arena-bot:local .
python -m simulation run -c configs/upstreams_heads_up.json --out results/isolated_upstreams \
  --runner docker --set execution.require_no_network=true
```

The host must expose the selected bot folder to its local Docker daemon. Read permission for the unprivileged UID is needed. These recipes target a Linux container runtime (including Docker Desktop’s Linux VM). The subprocess implementation was tested only on Linux; native Windows support is not claimed. WSL2 or a Linux VM is the supported Windows approach.

Runtime flags include `--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, an unprivileged user, PID limit 64, CPU limit 1, bounded memory/swap, CPU-time/file-descriptor ulimits, and a 64 MiB no-exec temporary filesystem. The Docker socket, engine code, other bots’ directories, result logs, and credentials are not mounted into a bot. The memory/CPU settings are configurable. The CPU-time budget is per worker/game, not per action.

Source downloads, pip installations, and Go compilation happen **before** matches. The source installer checks raw Git blob hashes against `sources.lock.json`, then checksums extracted declarations. A receipt records upstream paths, selected symbols, and SHA-256 hashes. That guards against accidental changes, not against malicious code in a deliberately approved upstream version. Review sources before running them, even if the hash matches.

The live installer download path was not executed in the delivery container. Its offline wrong-hash rejection, AST extraction, receipt loading, and Go compilation were exercised. The local source-excerpt verification mode is explicitly recorded, rather than mislabeled as verified full upstream downloads.

## Information hiding and anti-cheating

Workers receive player-specific observations. No opponent private card, burn card, future board, or dealer RNG is part of that contract. Admin `private_hands.jsonl` contains complete decks solely for replay verification. `config.json` and summaries record the resolved master seed after the run, so they must not be exposed to competing bots while the run is active. Result directories are created with owner-only permissions on POSIX where supported; that still does not protect them from same-user subprocesses.

For actual adversarial matches, use an unpredictable `seed: null`, keep it private while playing, do not expose the host project/results directory, and do not permit untrusted code in the parent process. A public fixed seed is for reproducible experiments, not secret-deck security. Swapped seats and seed control reduce certain confounds; they do not prevent collusion or eliminate random card variance.

Bot-provided counters such as `upstream_calls` are diagnostic, not trusted scoring inputs. Only the engine’s chip balances and tournament arithmetic determine ranks. A runtime-network declaration and a competition-eligibility flag are not audited facts.

## Operational limits

The protocol accepts at most 8 MiB/request and 1 MiB/response. Stdout is protocol-only. Stderr is a bounded tail in the parent; do not use unbounded tracing in a submitted bot. The same deadline covers a child that stops reading stdin and one that stops answering. Failed initialization is fatal. A timeout kills the process group; user cleanup callbacks are not guaranteed. Read-only execution prevents ordinary persistence, but any broader host/kernel security hardening and event audit remains the operator’s responsibility.
