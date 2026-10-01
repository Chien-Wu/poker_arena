# Poker Arena

A configurable **2–9-player no-limit Texas Hold’em** simulator, tournament runner, and versioned bot interface. Python 3.11+; the core and four native bots use only the standard library. Tested locally on Python 3.13 / Linux.

## Start here

```bash
cd poker_arena
python -m simulation run --config configs/quickstart.json --out results/first
```

Open `results/first/report.html` in a browser. No server, account, API key, model download, or network call is required for the native demonstration. Run commands from this project directory; output directories must be new.

The preset runs four rounds, with five seat-rotated games per group per round. A game is at most 20 hands in this quickstart; the default `GameConfig` is 100 hands. Heads-up tie-break games are additional and can materially increase runtime. Change `--hands`, `--rounds`, or other settings rather than editing the engine.

```bash
python -m simulation run -c configs/quickstart.json --out results/longer \
  --hands 200 --rounds 4 --seed 42 \
  --set game.initial_stack=5000 \
  --set players.0.params.raise_equity=0.60
```

`subprocess` is the default execution boundary: hard action deadlines and independent bot processes. It is **not a security sandbox**. For audited, untrusted submissions, use the supplied Docker/no-network profile; see `docs/SECURITY.md`. Docker execution was not exercised in the build environment.

## What the 60% integration coverage means

There are **12 adapters for 12 distinct repositories from the earlier 20-repository list (60% repository coverage)**. They invoke specifically named upstream policies through source extraction, not twelve copies of a new generic bot. However, several are a repository’s heuristic/reference agent, **not its advertised pretrained CFR/DeepCFR/DQN solver**. NoRegrets is blueprint-only and uses its upstream untrained check/call fallback by default. Do not interpret this as twelve full, pretrained flagship bots or evidence of playing strength.

The 12 adapters were exercised locally against source-inspected policy excerpts, in both heads-up seats, with real hand execution and replay checks. Only the Go handler’s entire upstream file was additionally checked against its pinned Git blob hash here. Full upstream downloads were not possible from the execution container; the included installer’s live download path and all-raw-source end-to-end integration remain unverified in this delivery. These limits are recorded in `verification/BUILD_REPORT.json` and `docs/TESTING.md`.

**Third-party sources and model files are not bundled in this ZIP.** To acquire the pinned original declarations and compile the Go policy, perform this explicit build-time step on a network-connected machine:

```bash
python -m pip install -r requirements-upstreams.txt
# Install Go >= 1.22 separately for the PokerForBots handler.
python tools/fetch_upstreams.py --all
python -m simulation validate-bot --all-upstreams --hands 20 \
  --out results/upstream_validation.json
python -m simulation run -c configs/upstreams_heads_up.json --out results/upstream_league
```

The installer fetches Git blobs by hash, checks the raw blob before extraction, retains the raw source locally, and writes a SHA-256 receipt. Missing source is a fatal startup error: it is not replaced by an unrelated fallback bot. `GITHUB_TOKEN` is optional at install time to avoid public API rate limits; never give it to match workers.

`configs/upstreams_heads_up.json` permits all twelve repository policies. Four have heads-up-only adapters, so they cannot enter a five-player table. `configs/upstreams_multiway.json` has the eight multi-player-capable upstream policies plus two native entries at two five-player tables. Table-size incompatibilities are rejected before play.

| Original # | Bot ID | Actual integrated policy | Seats |
|---:|---|---|---:|
| 4 | `up_fawz` | CFR-Poker-Bot `pot_odds_bot` reference heuristic | 2 |
| 5 | `up_jeffelin` | `strength_bot.Player`; betting-only projection, no discard game | 2 |
| 6 | `up_lucky` | `MonteCarloBot` | 2–9 |
| 7 | `up_ethan` | `PokerBot` heuristic mode; CFR disabled | 2–8 |
| 8 | `up_gongsta` | `EquityAIPlayer.get_action`, not `CFRAIPlayer` | 2 |
| 10 | `up_dberweger` | `StylePolicy` arena reference, not DeepCFR | 2–9 |
| 11 | `up_vincent` | `RandomAgent_mcts` reference, not DeepCFR | 2–6 |
| 12 | `up_dqn_reference` | `HeuristicPlayer`, not the DQN network | 2–9 |
| 14 | `up_noregrets` | Legacy blueprint policy; untrained unless JSON supplied | 2–9 |
| 15 | `up_fullhouse` | Reference `Shark.decide`, not later submission versions | 2–9 |
| 16 | `up_pokerforbots` | Original Go aggressive handler | 2–9 |
| 17 | `up_holdemlab` | `RuleBasedHeuristicAgent` | 2 |

Exact file paths, source hashes, data transformations, restrictions, and the eight unintegrated repositories are documented in `docs/INTEGRATIONS.md` and `sources.lock.json`.

## Project layout

```text
poker_arena/
  simulation/
    contracts.py          # Public Observation, Action, events, results
    sdk.py                # BaseBot and lifecycle callbacks
    engine.py             # Authoritative poker rules and chip accounting
    game.py               # Repeated hands, bot calls, error policy
    tournament.py         # Rotation, two-stage scoring, regrouping, playoffs
    execution.py          # In-process / subprocess / Docker execution
    registry.py           # Manifest discovery and compatibility checks
    experiments.py        # Repeat / resume / parameter sweeps
    replay.py             # Re-execute logged deals and actions
    report.py             # Offline HTML results
    __main__.py           # CLI
  bots/
    mybot1/
      bot.json
      adapter.py
      code/
        __init__.py
        strategy.py       # Put your own decision logic here
    up_lucky/
      bot.json
      adapter.py          # Canonical observation ↔ upstream representation
      code/upstream/      # Created by explicit source installer; not bundled
    ...
  utils/                  # Cards, equity, deterministic seeds, source loading
  configs/                # Native, heads-up, multiway, no-network, sweep presets
  docs/                   # Full bot format, mechanisms, configuration, tests
  schemas/                # Machine-readable v1 public schemas
  tests/
  tools/
  verification/           # Build results and sample completed tournament
```

## Future bots: one folder, no engine edits

```bash
python -m simulation new-bot my_new_bot
```

This creates `bots/my_new_bot/bot.json`, `adapter.py`, and `code/strategy.py`. Edit only your strategy and add an entry to the run configuration:

```json
{"id": "candidate_v2", "bot": "my_new_bot", "params": {"max_call": 40}}
```

`bot` identifies the code folder. `id` identifies an independent competitor instance. Multiple instances of one bot can have different parameters and independent memory/randomness.

The required callback is:

```python
from simulation.sdk import BaseBot, Action, Observation

class Bot(BaseBot):
    def act(self, obs: Observation) -> Action:
        if "check" in obs.legal_actions.types:
            return Action("check")
        return Action("fold")
```

For a raise, return `Action("raise", raise_to=120)`: **120 is your total contribution on the current street**, not 120 more chips and not your total contribution over the whole hand. Check/call/fold have no amount. All-in is a capped call or a raise to the hero’s remaining-stack-plus-street-contribution. The engine supplies legal bounds, including short-all-in exceptions.

The complete, explicit future-bot specification is in **`docs/BOT_FORMAT.md`**. It includes the input fields, lifecycle, state persistence, JSON Lines protocol for non-Python bots, example manifest, and information-security boundary.

## Repeat, sweep, inspect

```bash
# Repeat an entire tournament 10 times with separate reproducible seed streams.
python -m simulation batch -c configs/quickstart.json --iterations 10 --out results/batch

# Resume completed iterations without overwriting interrupted logs.
python -m simulation batch -c configs/quickstart.json --iterations 10 --out results/batch --resume

# Cartesian parameter sweep, 3 repeats per parameter combination.
python -m simulation sweep -c configs/quickstart.json --grid configs/grid.json \
  --iterations 3 --out results/sweep

python -m simulation list-bots
python -m simulation validate-bot --bot my_new_bot --hands 20
python -m simulation replay results/first/private_hands.jsonl
```

The supplied grid varies the first competitor’s raise-equity threshold and bet fraction. `aggregate.json` reports mean points, point standard deviation, mean rank, net chips, failures, and timeouts. Those results are experiment statistics—not equilibrium exploitability or a guaranteed win rate.

## Rules and limits

The supplied screenshot’s rotation, double conversion to rank points, four rounds, regrouping, and heads-up tie-break concept are implemented. The screenshot did not specify all poker mechanics; this project makes them explicit in `docs/RULES.md`. Notably: no rake/rebuy, stacks carry across hands within a game, stacks reset between games, all side pots and uncalled refunds are handled, and unresolved bounded playoffs are reported as shared ranks or aborts—not arbitrary winners.

The 48-hour construction window and team-size rules require a human submission audit. Existing imported policies are explicitly marked `competition_eligible: false`; these benchmark opponents are not eligible fresh submissions under the screenshot’s no-prior-code rule. Runtime LLMs and remote decision APIs are not integrated.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/verify_evaluator.py --out results/evaluator.json
```

Without installed upstream sources, twelve source-integration tests explicitly skip; core tests still run. After source installation, those tests exercise the real selected source declarations. The local build passed 247 tests using its inspected-source test cache, compared 15,000 five-/six-/seven-card hands with an independent reference evaluator, and exhaustively checked all 2,598,960 five-card hands by category. See `docs/TESTING.md` for the exact verification scope and remaining untested paths.
