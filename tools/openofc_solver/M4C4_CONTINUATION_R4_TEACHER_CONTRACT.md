# M4C4 — exact dealer-R4 teacher under a supplied continuation vector

## Purpose

M4C3 identified a subset of dealer/button R4 states whose next HU meta-state is action-invariant. Those states can be labeled exactly without knowing the Fantasy continuation values.

M4C4 removes that restriction once an explicit 50-state continuation vector `V` is supplied. Every legal dealer-R4 action is exhausted and scored as

`immediate Hero points + Hero-perspective V(exact next HU state)`.

The next state is produced by the existing exact Fantasy/re-Fantasy transition module. Therefore point-for-Fantasy trades are handled mathematically rather than by a heuristic bonus.

## Authority boundary

The R4 action comparison is exact **conditional on the supplied continuation vector**. M4C4 does not certify that `V` is itself correct.

This distinction is mandatory:

- with `V=0`, M4C4 reproduces the exact current-hand R4 oracle;
- with a nonzero `V`, M4C4 exactly propagates that vector through every legal R4 completion;
- no guessed Fantasy value is introduced;
- the teacher receives production authority only after the outer continuation solve certifies/fixes the vector used for training.

## Persistent identity mapping

The strategic hand engine uses relative roles `0=nondealer` and `1=dealer`. The continuation surface uses persistent player identities. M4C4 maps the dealer role to the current button owner, reconstructs persistent player-0/player-1 terminal boards, applies the exact next-state transition, and then converts persistent player-0 continuation value back to the acting Hero perspective.

## Distillation

`add_continuation_r4_teacher` emits a uniform target over all exactly tied Bellman-optimal actions. The SHA-256 holdout split remains enforced by default, so a held-out exact R4 state cannot silently enter replay.

## Strategic consequence

Once the outer 50-state continuation vector is solved, **all fully observed dealer R4 decisions become exact long-horizon training anchors**, including states where sacrificing immediate points is correct because it improves Fantasy/re-Fantasy continuation.

The remaining hard work for the normal-game AI is therefore pushed earlier in the hand and into the unsolved continuation kernels rather than left ambiguous at R4.
