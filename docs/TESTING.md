# Testing and evidence

## Reproduce the tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/verify_evaluator.py --out results/evaluator.json
```

The build environment was Linux, Python 3.13.5. The core requires Python 3.11+ by syntax/API usage; other interpreter/platform combinations were not exercised here. Source policies use NumPy 2.3.5 and the Go handler was compiled locally.

The local suite passed **247 tests**. Coverage includes canonical contract errors, immutability and private-card filtering; blind positions/short blind payments; all-in calls; full/short/cumulative raise reopening; dry-side-pot prevention; uncalled refunds; multiple side pots; tied pots and odd chips; fixed-seat bust-outs; 960 randomized 2–9-player hands with chip-conservation invariants; game-point versus round-point arithmetic; rotations/regrouping; bounded playoffs; deterministic replay and tamper rejection; native subprocess execution; timeout process termination; stalled-stdin deadline; constructor failure; fallback diagnostics; credential environment filtering; scaffolding; parameter sweeps and completed-iteration resume; pinned-source hash rejection; and twelve selected source-policy adapters.

Card evaluation is checked against a separately implemented five-card/combinations reference on **15,000 random five-/six-/seven-card inputs**. The exhaustive verifier evaluates **all 2,598,960 five-card combinations** and checks the exact category frequency histogram. Those checks do not constitute proof of every possible seven-card comparison or every poker house rule. The engine is an original implementation, not a certified external game server.

## Important source-integration distinction

The runtime container could not fetch full files from public GitHub, although the connected GitHub reader could expose source text for inspection. Local source-adapter tests therefore used **source-inspected/transcribed selected policy declarations**, with private extraction receipts marked `source_inspected_policy_excerpt`. They were not mock `act()` placeholders: the selected policy logic ran through real game hands and returned decisions. However, whole-file byte equality was not established for all Python repositories, and this is **not full-upstream-build verification**.

The complete Go aggressive handler was reconstructed and its whole-file Git blob SHA matched the locked upstream file. Its compiled Go decision code was invoked through the command protocol. Python code in the final ZIP consists of the project’s adapters/engine/SDK; third-party policy caches used in the local build are not included.

`tools/fetch_upstreams.py --all` is the production acquisition path: fetch each locked raw Git blob, verify its hash, AST-extract exactly the selected declarations, retain raw code locally, and create SHA-256 extraction receipts. Its live network download path was not run here. Offline hash rejection/extraction tests and local Go compilation were run. Consequently, the release should be described as **12 implemented repository-policy adapters tested in inspected-source mode**, not “12 fully validated pretrained poker solvers.”

After acquiring actual raw sources on your own machine:

```bash
python -m pip install -r requirements-upstreams.txt
python tools/fetch_upstreams.py --all
python -m pytest -q -m upstream
python -m simulation validate-bot --all-upstreams --hands 100 \
  --out results/raw_source_validation.json
```

Every source integration test requires actual decision calls, checks zero engine failures/timeouts, plays both HU seats, completes real hands, and verifies replay records. Source installation is opt-in: on a clean ZIP without source caches, twelve integration tests explicitly skip and the remaining core tests run. A skipped integration is not recorded as a pass or as an installed opponent.

Many policies are reference agents. In particular, the dberweger and Vincent policies are not their repositories’ DeepCFR checkpoints; `up_dqn_reference` is not a DQN; NoRegrets is untrained blueprint fallback unless supplied a local JSON strategy. No playing-strength, equilibrium, convergence, or leaderboard superiority claim is made.

## Deployment paths not verified here

Docker image build/runtime, actual network-denial/cgroup behavior, Windows/macOS native subprocess operation, live GitHub source installation, and unavailable flagship model/checkpoint inference were not tested in this environment. Docker flag construction and fail-closed no-network configuration are tested but are not substitutes for a deployment sandbox test.

The default native demonstration, source-policy smoke details, evaluator histogram, pytest XML/text, and build metadata are in `verification/`. Administrative eligibility (48-hour creation, team members, model provenance) requires human review. Test metrics are local integration evidence, not competition certification.
