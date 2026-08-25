# M4S — Strategic equilibrium / all-variable exactness contract

## Why the previous backward tree is not the final solver

M2b and M3a are legitimate teacher components under the belief stated in their
contracts: earlier reachability is card-blind, therefore unseen physical cards
are exchangeable conditional on the stored information set.  That assumption
stops being globally correct once earlier actions become strategic.

Example: if a dealer places one particular rank/suit pattern on R3 only when a
specific hidden packet is present, the non-dealer's R4 belief is no longer the
uniform distribution over every unseen 3-card dealer packet.  The public R3
placement is evidence.  A solver that keeps using a uniform hidden-card belief
would erase that evidence and can choose a different action from the true
information-game optimum.

Therefore M2/M3 backward teachers remain useful exact/sampled audit oracles, but
**they are not sufficient to certify a globally optimal normal-hand policy.**
The global policy must solve all information sets jointly so public actions
induce the correct posterior automatically.

## Game-theoretic target

For two-player normal OFC, ignoring table-stake caps and future Fantasy for one
moment, the hand is a finite two-player zero-sum extensive-form game with
chance and perfect recall.  The strategic target is a Nash equilibrium.

The v1 global trainer uses outcome-sampling Monte Carlo CFR with the complete
action set.  No opening placement or later place-2/discard-1 action is removed.
With sufficient sampling, MCCFR converges toward the equilibrium of this finite
game.  A finite run is not called "mathematically perfect" merely because the
code is game-theoretically correct; promotion requires measured exploitability
or an equivalent best-response bound.

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
the same.  Timing is strategic evidence: two identical current boards reached
through different prior placement histories can imply different hidden-card
posteriors.

## Chance / action order represented by the HU normal-hand core

The captured KKPoker rules establish five rounds.  Each player receives five
cards in the opening and must place all five.  R1-R4 deal three cards, place two
and privately discard one.  The player left of the dealer/button acts first and
action proceeds clockwise.  In heads-up this is non-dealer first, button/dealer
second on every round.

The training sampler draws one complete 34-card physical deal from the 54-card
Ultimate + Joker deck.  Future and opponent packets may be sampled internally,
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

The rule transition is now represented explicitly in `fantasy_transition.py`:

- normal valid top QQ/KK/AA -> 14/15/16-card Fantasy;
- normal valid top trips in Ultimate + Jokers -> 17-card Fantasy;
- while already in Fantasy, top trips OR bottom quads-or-better qualifies for
  re-Fantasy;
- Ultimate re-Fantasy keeps the same Fantasy card count;
- Progressive re-Fantasy returns 14 cards.

This module deliberately returns a **state transition, not a guessed number of
points**.  The global long-horizon objective must value those next-hand states
through solved play, not a manually selected Fantasy bonus.

## Variables still required before "all-variable exact" can be claimed

1. **Convergence / exploitability gate for HU current-hand MCCFR.**  Smoke tests
   prove information safety and mechanics only.  Ryzen-scale training, held-out
   best-response evaluation and multi-seed stability are required.
2. **Long-horizon Fantasy value.**  Couple normal-hand and 14/15/16/17-card
   Fantasy states and solve the continuation fixed point / average-reward game.
3. **Fantasy strategic information.**  A Fantasy player's all-at-once placement
   must respect exactly what is visible at the time the placement is locked;
   the exact 14-17 arrangement enumerator becomes a leaf/action oracle, not a
   universal-dominance heuristic.
4. **Both-player Fantasy states.**  Handle normal-vs-Fantasy, Fantasy-vs-normal,
   and both-in-Fantasy transitions according to KKPoker timing.
5. **Three-player mode.**  The KKPoker rules also define UTG/MP/BTN action order
   and three pairwise scoring comparisons.  Three-player strategic solving is
   a separate general multiplayer equilibrium problem and cannot be certified
   by a heads-up minimax solver.
6. **Table-fund win/loss cap.**  The scoring rules cap a player's win/loss by
   funds on the table at the start of the hand.  If the live game can reach a
   cap relevant to strategic choice, starting funds and settlement order must
   be part of the state and utility.
7. **Production distillation/integration.**  A fast policy is acceptable only
   if its measured loss against the search/training oracle remains below the
   promotion threshold; otherwise runtime keeps search/fallback.

## Promotion language

The following labels are reserved:

- `EXACT_TERMINAL`: terminal board/score is exhaustively exact.
- `EXACT_INFORMATION_SET`: a finite information-set expectation is exhaustively
  integrated under its explicitly stated belief.
- `STRATEGIC_APPROX`: equilibrium-oriented solver with nonzero/unmeasured
  exploitability.
- `STRATEGIC_CERTIFIED(epsilon)`: best-response exploitability is bounded by
  the published epsilon under the complete declared game model.
- `ALL_VARIABLE_CERTIFIED(epsilon)`: the strategic certificate also includes
  Fantasy continuation, relevant table caps, player-count mode and production
  policy loss.

Until the last certificate exists, no release note may call normal OFC play
"mathematically perfect".
