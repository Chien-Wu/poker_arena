# Integration register

## Scope and provenance

These are 12 distinct repository-policy integrations, not a claim that every previously advertised flagship bot is runnable. The adapters preserve selected upstream decision declarations; dependencies and engine representations are supplied through explicit facades. Consequently they are strategy-extraction integrations, not full original repository installations. Source selection is pinned in `sources.lock.json`.

Local validation used inspected-source excerpts, with the caveat documented in `TESTING.md`. The release does not bundle those excerpts. Run the pinned raw-source installer and upstream tests on a connected machine before relying on raw-source compatibility. No absent model or source is silently replaced. Imported code is benchmark-only, not a fresh 48-hour submission.

## 4. `up_fawz` — fawzmehfil/CFR-Poker-Bot

**Selected policy:** `pot_odds_bot`. Existing heuristic baseline, not a trained CFR policy.

**Supported seats:** 2–2. **Defaults:** `{"samples": 80}`.

**Input:** State facade with hero cards, public board/pot/stacks, legal_actions(), to_call(), rules.big_blind; hero-only uniform-card equity helper.

**Output and scope:** String action; bet/raise becomes the engine-supplied minimum full/legal raise target. All-in maps to stack cap.

Source evidence and pinned declarations:

- [holdem_cfr/holdem_eval/__init__.py](https://github.com/fawzmehfil/CFR-Poker-Bot/blob/main/holdem_cfr/holdem_eval/__init__.py) — Git blob `b5c34e20205a10b57d8299313d578223e28d3206`. Selected: `pot_odds_bot`.

## 5. `up_jeffelin` — jeffelin/CFR_pokerbot

**Selected policy:** `strength_bot.Player`. Heads-up betting-only projection of the 2026 discard-game reference policy; discard rounds are not simulated.

**Supported seats:** 2–2. **Defaults:** `{"samples": 80}`.

**Input:** MIT-style GameState/RoundState facades, pips/stacks/own two cards/board, hero index, legal action classes and raise_bounds(). Opponent hand is empty.

**Output and scope:** Fold/Check/Call/RaiseAction; amount is raise-to. No DiscardAction is advertised; this is an explicit betting-only NLHE projection, not the original discard competition.

Source evidence and pinned declarations:

- [engine-2026/tuff_model/strength_bot/player.py](https://github.com/jeffelin/CFR_pokerbot/blob/main/engine-2026/tuff_model/strength_bot/player.py) — Git blob `66e21d6f8ceefc5f9b8c6fdf107eed4eb77b757e`. Selected: `card_rank`, `card_suit`, `hand_strength`, `choose_discard`, `decide_action`, `Player`.

## 6. `up_lucky` — luckyone18/Poker

**Selected policy:** `MonteCarloBot`. Actual Monte Carlo policy. Original multiway ties are valued at one half, preserved.

**Supported seats:** 2–9. **Defaults:** `{"samples": 80}`.

**Input:** PlayerView-like object with own cards/board, pot, to_call, positions, stacks and legal action ranges; evaluator/deck representation facade.

**Output and scope:** Action(type,amount); canonical raise-to. Original half-credit treatment of multiway ties is preserved in its own Monte Carlo policy, rather than silently improving it.

Source evidence and pinned declarations:

- [bots/monte_carlo_bot.py](https://github.com/luckyone18/Poker/blob/main/bots/monte_carlo_bot.py) — Git blob `8b0dd528ef08539ecf009c3d06645306c6e9de1c`. Selected: `MonteCarloBot`.

## 7. `up_ethan` — ethangarofalo/hold-em-bot

**Selected policy:** `PokerBot (heuristic mode)`. Original heuristic mode, no loaded CFR table and no opponent-model updates. Shared equity evaluator is the dependency facade.

**Supported seats:** 2–8. **Defaults:** `{"samples": 80}`.

**Input:** Explicit decide arguments: hero/board, pot, uncapped to_call, stack, position, live opponents, street, raise count. MC equity uses the shared helper, capped by samples.

**Output and scope:** Action enum and amount. Amount interpreted as newly paid chips, then converted by adding the existing street contribution. CFR and opponent-profile branches remain disabled in this integration.

Source evidence and pinned declarations:

- [info_sets.py](https://github.com/ethangarofalo/hold-em-bot/blob/main/info_sets.py) — Git blob `a12478f1a03e4db220959c24972d5587a7eb6b97`. Selected: `BoardTexture`, `SPRBucket`, `classify_board_texture`, `classify_spr`.

- [bot.py](https://github.com/ethangarofalo/hold-em-bot/blob/main/bot.py) — Git blob `b656fdc498bcdf589ff41ca20c80fc28d09386d1`. Selected: `Action`, `Position`, `PREMIUM_HANDS`, `STRONG_HANDS`, `PLAYABLE_HANDS`, `_hand_category`, `PokerBot.__init__`, `PokerBot.decide`, `PokerBot._preflop_decision`, `PokerBot._postflop_decision`.

## 8. `up_gongsta` — Deltebrain/Gongsta-AI

**Selected policy:** `EquityAIPlayer.get_action`. Equity reference policy, not CFRAIPlayer. GUI, speech and training artifacts deliberately excluded.

**Supported seats:** 2–2. **Defaults:** `{"samples": 80}`.

**Input:** Explicit EquityAIPlayer arguments: cards, board, pot, highest current bet, BB, remaining stack, dealer flag, checkAllowed. Shared heads-up equity helper.

**Output and scope:** f/k/c/b<number> strings; b is current-street raise-to, followed by metered legality adjustment. No GUI, speech engine, or CFR joblib artifacts imported.

Source evidence and pinned declarations:

- [src/aiplayer.py](https://github.com/Deltebrain/Gongsta-AI/blob/main/src/aiplayer.py) — Git blob `75d375256c34f8463b1328e8f61175c2c81faaf3`. Selected: `getAction`, `EquityAIPlayer.get_action`.

## 10. `up_dberweger` — dberweger2017/deepcfr-texas-no-limit-holdem-6-players

**Selected policy:** `StylePolicy`. Card-aware style/reference policy, not the DeepCFR neural checkpoint.

**Supported seats:** 2–9. **Defaults:** `{"samples": 80, "style": "tight_aggressive"}`.

**Input:** Observation-shaped facade with actor/seat, hole/board, pot, public players and LegalActions. Original StylePolicy/hand_score/pot_raise declarations execute with a shared hand evaluator.

**Output and scope:** Action(kind,raise_to). Styles are tight_passive, loose_passive, tight_aggressive, loose_aggressive, pot_pressure, train_pressure. Not its neural policy.

Source evidence and pinned declarations:

- [src/arena/heuristics.py](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players/blob/main/src/arena/heuristics.py) — Git blob `29278f868e3b3d6181a4980a9d2439e44a989747`. Selected: `Style`, `STYLES`, `hand_score`, `pot_raise`, `StylePolicy`.

## 11. `up_vincent` — goddamnVincent/6_players_no_limit_texas_holdem_deepcfr_agent

**Selected policy:** `RandomAgent_mcts`. Existing MCTS-named Monte Carlo baseline, not DeepCFR. Original policy hardcodes two simulated opponents and selects argmax.

**Supported seats:** 2–6. **Defaults:** `{"samples": 80}`.

**Input:** pokers-like state/player/card facade, active flags, public board, bets, stacks, legal enums. Original RandomAgent_mcts runs; its get_mcts_result dependency uses the local uniform-card outcome sampler.

**Output and scope:** (pkrs.Action, diagnostic). Raise amount is additional raise ABOVE the current wager, not pay-now. Original fixed +50 raise policy and hard-coded two-opponent equity query are preserved; engine bounds repair undersized requests.

Source evidence and pinned declarations:

- [src/agents/random_agent_mcts.py](https://github.com/goddamnVincent/6_players_no_limit_texas_holdem_deepcfr_agent/blob/main/src/agents/random_agent_mcts.py) — Git blob `10a9ac80d10af0edcd574227d4fb334a9e9602a1`. Selected: `stage_names`, `RandomAgent_mcts`.

## 12. `up_dqn_reference` — alexherm0123verify/poker-DQN

**Selected policy:** `HeuristicPlayer`. PyPokerEngine heuristic reference, not DQN weights. Original hardcoded nine-player equity assumption is preserved.

**Supported seats:** 2–9. **Defaults:** `{"samples": 80}`.

**Input:** PyPokerEngine valid_actions/hole_card/round_state facades with suit-first cards. Shared equity helper replaces the framework utility, not the HeuristicPlayer decision body.

**Output and scope:** (action,amount). This policy returns call/fold. Its original hard-coded nine-player equity setting is preserved. The DQN network is not loaded.

Source evidence and pinned declarations:

- [scripts/PlayerModels.py](https://github.com/alexherm0123verify/poker-DQN/blob/main/scripts/PlayerModels.py) — Git blob `dc88fae770f67dea8838819da4b3f1ef6f8e7de6`. Selected: `HeuristicPlayer`.

## 14. `up_noregrets` — conorarmstrong/noregrets

**Selected policy:** `legacy PluribusBot.get_action (blueprint-only)`. Untrained unless a JSON blueprint is supplied. Default executes the upstream empty-blueprint check/call fallback; no strength claim.

**Supported seats:** 2–9. **Defaults:** `{"blueprint": null}`.

**Input:** Legacy state with only the hero hole-card mapping, public board/pot/seat/bets/stacks, plus blueprint get_average_strategy. No hidden opponent cards invented; real-time search is off.

**Output and scope:** (Action,amount). Default blueprint is empty: its own call fallback executes. Optional blueprint parameter is a JSON file relative to code/, mapping the original string infoset key to records {action: enum name, amount: integer, weight: number}. No training or strength is implied.

Source evidence and pinned declarations:

- [legacy/poker_bot_pluribus.py](https://github.com/conorarmstrong/noregrets/blob/main/legacy/poker_bot_pluribus.py) — Git blob `65ac56d959627afa58818750ab8d12354008f7be`. Selected: `Action`, `InfoSet`, `LinearMCCFR.get_average_strategy`, `PluribusBot.get_action`, `PluribusBot._get_info_set`, `PluribusBot._encode_betting_history`, `PluribusBot._sample_from_strategy`.

## 15. `up_fullhouse` — BouillieAnonymous/4fullhousehackathon

**Selected policy:** `Shark.decide`. Shark reference policy, not the separately packaged 13.x submission.

**Supported seats:** 2–9. **Defaults:** `{"samples": 80}`.

**Input:** Dictionary containing street, amount_owed, pot, your_stack, seat_to_act, players, your_cards, min_raise_to, your_bet_this_street, can_check.

**Output and scope:** {action,amount}; raise amount is raise-to. Original simple reference Shark is invoked, not the later Fullhouse submission.

Source evidence and pinned declarations:

- [docs/official-fullhouse-engine/bots/shark/bot.py](https://github.com/BouillieAnonymous/4fullhousehackathon/blob/main/docs/official-fullhouse-engine/bots/shark/bot.py) — Git blob `59004d4585f9863954f6fb4ef469dceec27b6ad1`. Selected: `STRONG_HANDS`, `hand_strength`, `decide`.

## 16. `up_pokerforbots` — lox/pokerforbots

**Selected policy:** `aggressive.Handler.OnActionRequest (Go)`. Actual Go handler, compiled with a minimal local SDK facade. Seeded PCG constructor added beside the unmodified source.

**Supported seats:** 2–9. **Defaults:** `{}`.

**Input:** Command-process bridge creates protocol.ActionRequest.ValidActions and MinBet; uses merged call/check vocabulary. Selected upstream handler ignores GameState.

**Output and scope:** Original Go aggressive handler returns string/int/error. A small local Go SDK shape facade avoids fetching an entire server, and a seeded constructor makes its RNG reproducible. The decision function itself is unchanged.

Source evidence and pinned declarations:

- [sdk/bots/aggressive/handler.go](https://github.com/lox/pokerforbots/blob/main/sdk/bots/aggressive/handler.go) — Git blob `52bb6452a579bd88ecc1c8df6c77e49d43060952`. Selected: complete Go handler.

## 17. `up_holdemlab` — HFossdal/poker-game-simulator

**Selected policy:** `RuleBasedHeuristicAgent`. Heads-up rule-based reference policy; not the CFR policy. Adapter supplies its abstract legal-action menu.

**Supported seats:** 2–2. **Defaults:** `{"samples": 80}`.

**Input:** PlayerObservation-shaped facade with rich cards, public money/positions, concrete legal bet-size menu, and abstract vocabulary. Original rule-based policy, helpers, and pick_abstract execute.

**Output and scope:** Legacy Action(action_type,amount) becomes canonical raise-to; ALL_IN maps to a raise or capped call. The adapter supplies a legal menu derived from the original abstract size vocabulary, not the full original engine.

Source evidence and pinned declarations:

- [src/holdem/agents/tight_aggressive.py](https://github.com/HFossdal/poker-game-simulator/blob/main/src/holdem/agents/tight_aggressive.py) — Git blob `4585f2fe0446bde78eeed223e50d305c6406a906`. Selected: `_preflop_strength`, `_postflop_equity_estimate`.

- [src/holdem/agents/action_abstraction.py](https://github.com/HFossdal/poker-game-simulator/blob/main/src/holdem/agents/action_abstraction.py) — Git blob `fda77ab3470612b99b5abdaea5a49c6093dcf66e`. Selected: `pick_abstract`, `_closest_bet_or_raise`.

- [src/holdem/agents/rule_based.py](https://github.com/HFossdal/poker-game-simulator/blob/main/src/holdem/agents/rule_based.py) — Git blob `5ebc5966215e9af489eeaf7d11e124babe963f6e`. Selected: `RuleBasedHeuristicAgent`.


## The eight not integrated

| Original # | Repository | Why it is not counted |
|---:|---|---|
| 1 | Nemandza82/g5-poker-bot | Native/.NET components and opponent/model data were not built and exercised here. An ACPC parser alone would not be the G5 bot. |
| 2 | AI-Decision/DecisionHoldem | Stateful native search/blueprint library and data not installed. A getdecision signature is not a working solver. |
| 3 | fedden/poker_ai | Verified training path uses a reduced T–A deck/fixed-limit game and strategy storage, not a general plug-in NLHE decision bot. |
| 9 | lbn187/PokerSkill | Live LLM decision calls conflict with the supplied no-runtime-AI/API rule. Not replaced by a fake local LLM result. |
| 13 | UtGong/texas-holdem-deep-rl | Notebook/RLCard agents with variant-specific observation/action encodings; full NLHE runtime agent/checkpoint not verified. |
| 18 | zanussbaum/pluribus | Primarily Leduc/CFR research code in the inspected tree; no verified general NLHE bot callback. |
| 19 | c-heidt/pluribus-opponent-exploitation | SearchAgent needs its blueprint store and substantial environment/search lifecycle. No fake blueprint or hidden-card state was supplied. |
| 20 | IncrediblyHungie/Poker-Project | Repository/callback could not be retrieved reliably in the source audit; not counted from a README claim. |

## What is not measured

A successful callback or a completed tournament establishes a local interface exercise, not strategic equivalence to another engine, compatibility with every upstream feature, or playing strength. Adapter-specific projections and changed helper budgets affect play. `adapter_repairs` records size/legal-action corrections; the engine does not hide those corrections as clean native play. `upstream_calls` confirms that the selected policy was invoked, not that a pretrained model was loaded. In-process facades are for trusted code; use the subprocess/Docker boundary for independent execution.
