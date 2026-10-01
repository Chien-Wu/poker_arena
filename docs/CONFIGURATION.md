# Configuration and iterative experiments

All configs are JSON. Unknown configuration fields and invalid values are rejected. IDs are stable strings; chips/counts are integers, not booleans or floats. `python -m simulation --help` and each subcommand’s `--help` list the CLI.

## Game parameters (defaults)

| Path | Default | Meaning |
|---|---:|---|
| `game.initial_stack` | 2000 | Reset stack per competitor at game start |
| `game.small_blind` | 10 | Starting small blind |
| `game.big_blind` | 20 | Starting big blind / minimum full opening wager |
| `game.ante` | 0 | Uniform per-player dead ante |
| `game.hands_per_game` | 100 | Cap per game; bust-outs can end it sooner |
| `game.max_actions_per_hand` | 2000 | Abort pathological hands beyond this operational limit |
| `game.blind_schedule` | `[]` | Ordered blind/ante levels by one-based hand number |

Blind-schedule example:

```json
[
  {"from_hand": 51, "small_blind": 20, "big_blind": 40, "ante": 0},
  {"from_hand": 101, "small_blind": 40, "big_blind": 80, "ante": 5}
]
```

All four keys are required in each level. `from_hand` must be strictly increasing. A new game starts at the original blinds; tie-break legs omit the blind schedule.

## Tournament parameters

| Path | Default | Meaning |
|---|---:|---|
| `tournament.rounds` | 4 | Rounds per tournament |
| `tournament.group_size` | 5 | Target maximum group size, balanced without singletons |
| `tournament.rotation_cycles` | 1 | Complete n-game seat cycles per n-player group |
| `tournament.regroup` | true | Reassign groups by cumulative round-point ranks |
| `tournament.require_equal_groups` | false | Reject unequal group sizes when true |
| `tournament.tiebreak_hands` | 20 | Hands per swapped-seat playoff leg |
| `tournament.tiebreak_attempts` | 3 | Bounded repeated playoff attempts for unresolved subsets |
| `tournament.tiebreak_scope` | `all` | `all` ranking stages, or exploratory `final` only |
| `tournament.unresolved_ties` | `share` | Share occupied ranks/points, or `error` to abort |

The quickstart changes hands per game to 20 and tie-break hands to 10. Source presets use 30 hands per game and failure policy `abort`. Round/group settings are independent of poker hand settings.

## Execution parameters

`runner` is `subprocess` (default), `inprocess`, or `docker`. Default budgets: action 2000 ms, startup 20000 ms, event 2000 ms, 3 failures/game, memory 2048 MiB, CPU time 120 seconds/worker. `failure_policy` is `check_fold` or `abort`. `require_no_network` defaults false, and requires Docker when true. Default image is `poker-arena-bot:local`.

Heavy local models/long games can need a larger startup, memory, or CPU budget. Increasing an action budget is explicit; no adapter silently receives extra time. In-process deadlines detect overruns only after return.

## Entries and parameters

```json
{"id": "my_candidate", "bot": "mybot1", "params": {
  "equity_samples": 80,
  "raise_equity": 0.65,
  "bet_fraction": 0.6,
  "call_margin": 0.02,
  "bluff_frequency": 0.02
}}
```

Those parameter names belong to the native example policy; they are not global poker rules. Most upstream adapters use `samples` for their Monte Carlo helper budget. The dberweger adapter also accepts a named style; NoRegrets accepts an optional local JSON `blueprint` path. See individual `bot.json` defaults and `docs/INTEGRATIONS.md`.

Dotted overrides may address nested lists:

```bash
python -m simulation run -c configs/quickstart.json --out results/variant \
  --set players.0.params.equity_samples=200 \
  --set players.0.params.raise_equity=0.70 \
  --set tournament.tiebreak_scope=final
```

Values are parsed as JSON where possible; bare strings are accepted. Common shortcuts are `--hands`, `--rounds`, `--seed`, and `--runner`.

## Iterative use

`batch` repeats entire tournaments with fresh instances. A single resolved master seed deterministically derives separate iteration seeds and, within them, separate shuffle/deal/policy seeds. Supply `--seed 42` to reproduce, or JSON `seed: null` to generate a new unpredictable master. Resolved configuration is saved.

```bash
python -m simulation batch -c configs/quickstart.json --iterations 20 --out results/experiment
python -m simulation batch -c configs/quickstart.json --iterations 20 --out results/experiment --resume
```

Resume requires identical resolved configuration, requested iteration count, and bot-folder fingerprints. It reuses complete iterations and preserves interrupted directories under `.interrupted.N` before rerunning them. It does not resume in the middle of a poker hand/round. Do not concurrently write to one experiment directory. The per-round checkpoint is an audit snapshot, not a promise of mid-game recovery.

`sweep` takes a Cartesian grid of dotted parameter paths. Each variant uses the same experiment seed stream for comparison, but divergent folds, bust-outs, rankings, and regrouping change later trajectories. This is **not duplicate poker** and is not a fully paired causal experiment.

```json
{
  "players.0.params.raise_equity": [0.55, 0.65, 0.75],
  "players.0.params.bet_fraction": [0.5, 0.75]
}
```

```bash
python -m simulation sweep -c configs/quickstart.json --grid configs/grid.json \
  --iterations 5 --out results/search
```

For Python control, see `examples/iterative_experiment.py`. `Config`, `override`, `Tournament`, `repeat`, and `sweep` are callable APIs. No UI or daemon is required.

## Outputs

Each tournament writes resolved config/provenance, per-action diagnostics, public hand results, private replay records, per-game results, playoffs, round checkpoint, summary JSON, leaderboard CSV, and offline `report.html`. Fault files exist only if faults occur. The batch directory adds `experiment.json`, `progress.json`, and `aggregate.json`; sweeps add `sweep.json` and per-variant directories.

Rank is determined by round placement points. `qualifier_net_chips` excludes playoff games. `qualifier_hands_at_table` counts hands played at the table, including hands after that seat busts; it is not a count of hands personally dealt. Counts and `adapter_repairs` diagnose integration behavior, not algorithmic quality. No solver exploitability metric is claimed.
