# M4S — HU strategic equilibrium / all-variable exactness contract

## Scope freeze: heads-up only

The strategic solver scope is permanently **heads-up (HU)** for this project.
Three-player OFC is outside the target game and must not consume training,
certification or production-integration effort. Shared scoring utilities may
retain regression coverage for generic code, but no three-player equilibrium,
three-player continuation value or three-player production policy is required
for M4S completion.

## Why the previous backward tree is not the final solver

M2b and M3a are legitimate teacher components under the belief stated in their
contracts: earlier reachability is card-blind, therefore unseen physical cards
are exchangeable conditional on the stored information set. That assumption
stops being globally correct once earlier actions become strategic.

Example: if a dealer places one particular rank/suit pattern on R3 only when a
specific hidden packet is present, the non-dealer's R4 belief is no longer the
uniform distribution over every unseen 3-card dealer packet. The public R3
placement is evidence. A solver that keeps using a uniform hidden-card belief
would erase that evidence and can choose a different action from the true
information-game optimum.

Therefore M2/M3 backward teachers remain useful exact/sampled audit oracles, but
**they are not sufficient to certify a globally optimal normal-hand policy.**
The global policy must solve all information sets jointly so public actions
induce the correct posterior automatically.

## Game-theoretic target

For two-player normal OFC, ignoring table-stake caps and future Fantasy for one
moment, the hand is a finite two-player zero-sum extensive-form game with
chance and perfect recall. The strategic target is a Nash equilibrium.

The global trainer uses outcome-sampling Monte Carlo CFR with the complete
action set. No opening placement or later place-2/discard-1 action is removed.
With sufficient sampling, MCCFR converges toward the equilibrium of this finite
game. A finite run is not called "mathematically perfect" merely because the
code is game-theoretically correct; promotion requires measured exploitability
or an equivalent best-response bound.

## Practical-feasibility contract

Mathematical rigor is required, but the solution must remain executable on the
available workstation rather than exist only as a theoretical construction.
The solver therefore follows this optimization order:

1. exact game automorphisms and canonicalization (currently the certified
   24-way suit symmetry);
2. exact memoization/transposition reuse that does not merge strategically
   different information states;
3. sampling methods such as MCCFR that preserve the declared equilibrium target;
4. resumable checkpoints, independent seeds, sharding and CPU parallelism;
5. exact late-round teachers/oracles where they reduce variance or certification
   cost without changing the target game;
6. only after those avenues are exhausted may an approximation be introduced,
   and then it is never allowed to inherit an exactness label unless its loss is
   separately bounded against the unabstracted oracle.

A training design that exceeds practical CPU, RAM, disk or wall-clock budgets is
not accepted merely because it is formally correct. Before every major scale-up,
a resource probe must measure throughput, information-set growth, memory use and
checkpoint size on the target machine. Scale increases are logarithmic and may
be stopped early when projected cost is disproportionate to measured policy or
exploitability improvement.

The final production policy may be distilled or cached for speed only when its
measured loss against the certified search/training oracle is below the declared
promotion threshold. Otherwise runtime keeps the stronger search/fallback path.

## Information-state contract

An information state may contain only information the acting player actually
has:

- seat/position and round;
- both public boards;
- the acting player's current private packet;
- the acting player's own prior discarded cards;
- the complete public placement history, including which public cards were put
  in which rows on each earlier action.

It must never contain:

- the opponent's current hidden packet;
- the opponent's private discards;
- undealt future cards;
- a future board or future action;
- a sampled determinization identifier.

The full public placement history is required even when the current board is
the same. Timing is strategic evidence: two identical current boards reached
through different prior placement histories can imply different hidden-card
posteriors.

## Chance / action order represented by the HU normal-hand core

The captured KKPoker rules establish five rounds. Each player receives five
cards in the opening and must place all five. R1-R4 deal three cards, place two
and privately discard one. The player left of the dealer/button acts first and
action proceeds clockwise. In heads-up this is non-dealer first, button/dealer
second on every round.

The training sampler draws one complete 34-card physical deal from the 54-card
Ultimate + Joker deck. Future and opponent packets may be sampled internally,
but they are excluded from the acting player's information-state key.

## Terminal exactness retained

Every sampled trajectory terminates in the certified Python evaluator:

- 3/5/5 row ordering and foul;
- KKPoker royalties;
- scoop;
- row-local two-Joker semantics;
- Fantasy entry metadata.

No neural approximation is used at a terminal leaf.

## Fantasy / re-Fantasy continuation

The rule transition is represented explicitly in `fantasy_transition.py`:

- normal valid top QQ/KK/AA -> 14/15/16-card Fantasy;
- normal valid top trips in Ultimate + Jokers -> 17-card Fantasy;
- while already in Fantasy, top trips OR bottom quads-or-better qualifies for
  re-Fantasy;
- Ultimate re-Fantasy keeps the same Fantasy card count;
- Progressive re-Fantasy returns 14 cards.

This module deliberately returns a **state transition, not a guessed number of
points**. The global long-horizon objective must value those next-hand states
through solved play, not a manually selected Fantasy bonus.

## Variables still required before "all-variable exact" can be claimed

1. **Convergence / exploitability gate for HU current-hand MCCFR.** Smoke tests
   prove information safety and mechanics only. Ryzen-scale training, held-out
   best-response evaluation and multi-seed stability are required.
2. **Long-horizon Fantasy value.** Couple normal-hand and 14/15/16/17-card
   Fantasy states and solve the continuation fixed point / average-reward game.
3. **Fantasy strategic information.** A Fantasy player's all-at-once placement
   must respect exactly what is visible at the time the placement is locked;
   the exact 14-17 arrangement enumerator becomes a leaf/action oracle, not a
   universal-dominance heuristic.
4. **Both-player Fantasy states in HU.** Handle normal-vs-Fantasy,
   Fantasy-vs-normal and both-in-Fantasy transitions according to KKPoker timing.
5. **Table-fund win/loss cap, if strategically reachable in HU.** If the live
   game can reach a cap relevant to strategic choice, starting funds and the HU
   settlement rule must be part of the state and utility. If field evidence
   proves the cap is never strategically reachable in the target configuration,
   document that and remove it from the strategic state rather than simulate an
   irrelevant variable forever.
6. **Production distillation/integration.** A fast policy is acceptable only if
   its measured loss against the search/training oracle remains below the
   promotion threshold; otherwise runtime keeps search/fallback.
7. **Resource feasibility.** A target epsilon is promoted only if the measured
   training/certification path fits the declared CPU/RAM/disk budget on the
   available workstation. If the cost curve becomes prohibitive, optimization
   must first use exact reductions or variance reduction rather than silently
   changing the game.

## Promotion language

The following labels are reserved:

- `EXACT_TERMINAL`: terminal board/score is exhaustively exact.
- `EXACT_INFORMATION_SET`: a finite information-set expectation is exhaustively
  integrated under its explicitly stated belief.
- `STRATEGIC_APPROX`: equilibrium-oriented solver with nonzero/unmeasured
  exploitability.
- `STRATEGIC_CERTIFIED(epsilon)`: best-response exploitability is bounded by
  the published epsilon under the complete declared HU game model.
- `ALL_VARIABLE_CERTIFIED(epsilon)`: the HU strategic certificate also includes
  Fantasy continuation, any strategically relevant HU table cap and production
  policy loss.

Until the last certificate exists, no release note may call normal OFC play
"mathematically perfect".
