# Game and tournament mechanisms

## Scope

The user-supplied “Rules and format” screenshot defines the tournament organization, not a complete poker ruleset. This implementation therefore records its own explicit rule profile: `nlhe-moving-button-v1`. It is a simulator for research and competition preparation, not certification that a particular organizer will accept a submission.

## Poker hand

52 distinct cards; two private cards per player; a three-card flop, one-card turn, and one-card river, with a burn before each public deal. At showdown the best five of seven cards determine each eligible player’s rank. Integer chips; no rake, fee, rebuy, straddle, bounty, ICM payout, or alternate deck. Supported table capacity is 2–9.

The button moves to the next occupied seat after a hand. Busted slots remain stable in observations but are skipped in dealing and action order. In heads-up the button posts the small blind and acts first preflop; the big blind acts first postflop. With at least three players, the first active seat after the big blind acts preflop and the first after the button acts postflop.

Uniform antes are dead contributions, distinct from street bets. Blind payments are capped by stacks. A partial big blind does not lower the nominal bring-in when multiple funded players can still contest the street. A lone funded player facing all-in opponents cannot open an uncontested side pot; it can only meet actual outstanding contributions or fold.

The actor may fold, check when owing nothing, call for up to its remaining stack, or raise within the supplied interval. No-limit opening minimum is the nominal big blind. A full raise must increase the current wager by at least the previous full raise increment. Under-minimum raises are allowed only as all-ins. After a short postflop opening of 10 with a 20 big-blind minimum, an unacted player’s ordinary minimum raise is to 30 (10 + 20), not a completion to 20. A short all-in does not reopen a player who has already acted unless the cumulative extra amount faced reaches the full increment. The per-player `acted_at` record is used, not one global “last action” boolean.

This profile also requires a previously checked player to face a full opening amount before it may raise again after an incomplete all-in opening. Different house interpretations should be implemented as an explicitly versioned profile, not a silent behavior change. The TDA’s reopening/full-bet rules were consulted as a reference, but the project is not a complete TDA implementation. Reference: https://www.pokertda.com/view-poker-tda-rules/ .

## Settlement and private information

At street close, any unmatched excess above the second-highest contribution is refunded. Contributions are layered into main/side pots, with folded players’ chips retained but those players excluded from eligibility. Adjacent layers having identical eligible players are merged **before** splitting tied payouts; splitting such artificial sub-layers separately would misallocate odd chips.

Each real pot is awarded among its eligible best hands. Odd chips in a tied pot go clockwise starting after the button. If everybody but one player folds, that player takes the contested money without showing private cards. If a showdown is needed, this profile shows all nonfolded players’ cards, including losing hands. Folded cards stay hidden.

The engine checks nonnegative stacks and chip conservation after state transitions and settlement. Admin replay logs contain the full dealt deck and must remain private. Normal bot observations and public result records do not contain the deck or folded cards.

## Hand versus game versus round versus experiment

A **hand** is one deal through settlement. A **game** is a sequence of hands, with chips carried over, ending at the configured hand cap or when fewer than two players have chips. Initial stacks reset for the next game. Blind levels optionally increase by hand number within a game.

A **round** assigns bots to groups and runs complete seat-rotation cycles inside each group. An **experiment iteration** is one complete tournament (normally four rounds), with fresh instances and an independent deterministic seed stream.

## Screenshot scoring, exactly two conversions

For a five-player group:

1. Play five games; rotate seat assignment once between games so every entry occupies each table seat once.
2. Rank final chip counts separately in each game. Ranks 1–5 receive game points 5, 4, 3, 2, 1.
3. Sum those five game-point scores for each bot. Rank the five totals. Convert ranks to round placement points 5, 4, 3, 2, 1 **again**.
4. Add only the round placement points to the cumulative tournament score. Raw chip profit and the first-stage game-point totals are not added to that cumulative score.
5. Regroup by descending cumulative round points before the next round. The highest scorers form the first group, the next tier the next group, and so on.
6. After four rounds, rank cumulative round placement points. The software records ranks but does not award money or claim prize eligibility.

Example: in one group, summed game points might be A=21, B=18, C=14, D=12, E=10. That round adds A=5, B=4, C=3, D=2, E=1 to the tournament. A’s final tournament score is not 21.

When a group has n rather than five bots, it plays n games per rotation cycle and uses n..1 points. This is an explicit completion of the screenshot’s “about five” wording: every bot still visits every seat. `rotation_cycles` can multiply those games. Groups are balanced without singletons: 12 bots at target group size 5 become 4/4/4; 11 become 4/4/3. For unequal groups, raw n..1 scales follow the screenshot and can affect comparability. `require_equal_groups=true` rejects unequal sizes rather than hiding that effect.

## Tie-break definition and termination

Default `tiebreak_scope="all"` resolves ties encountered at chip ranking, group game-point ranking, cumulative regrouping, and final placement. Two tied entries play heads-up with swapped-seat legs. A tie among more than two entries is a heads-up round-robin, also with swapped seats for each pair. Pairwise net chip difference over the two legs determines the playoff win; a zero difference contributes half a win each. Remaining tied subsets repeat, bounded by `tiebreak_attempts`.

Playoffs start fresh stacks and bot instances, use fixed starting blinds, and use `tiebreak_hands` per leg. They order tied scores but do not add tournament points or contaminate qualifier chip-profit statistics. They use distinct deals, not identical duplicate-poker deals; swapping seats does not remove card variance.

A finite program cannot guarantee that identical passive bots ever stop tying. On reaching the attempt cap, `unresolved_ties="share"` records a shared rank and averages occupied-rank points; `"error"` stops the run. It never invents a winner by alphabetical order or random draw. Shared groups are displayed in stable ID order only; that display ordering is not a win.

For faster exploratory work, `tiebreak_scope="final"` shares intermediate tied-point ranks and plays heads-up playoffs only for final cumulative placement. **That is a deliberate research deviation from the default tie interpretation**, not the strict preset. Final rank-point scores can differ between those profiles.

## Failures

Canonical illegal actions, exceptions, malformed protocol output, and timeouts are recorded. Under `check_fold`, the fallback is check when free, otherwise fold; after the failure budget a bot is disabled for the rest of that game. A killed timeout worker is disabled immediately. Under `abort`, any such failure aborts the game. Constructor failure or unavailable source/model artifacts always abort startup; no placeholder opponent is substituted.

A pathological hand that exceeds `max_actions_per_hand` aborts rather than force-awarding an invented pot. This is an operational limit, not a poker raise cap.

## Administrative rules

The provided folder template gives a uniform submission format. Team sizes of 1–4 and the 48-hour/no-prior-code window need organizer-side audit. The bundled native examples and imported benchmark code already exist before a future event, so they must not be misrepresented as new eligible submissions. `competition_eligible` is metadata only. No runtime external AI/LLM service is integrated, and the Docker profile removes network access; local model eligibility still depends on the organizer’s exact rules.
