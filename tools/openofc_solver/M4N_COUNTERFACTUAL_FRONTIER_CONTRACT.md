# M4N — exact Fantasy counterfactual frontier

## Purpose

M4M establishes that Fantasy-vs-Fantasy HU placement is sealed: the real policy
knows its own Fantasy packet and public meta-state, not the opponent's hidden
packet or completed board.

M4N adds an **offline poker teacher** for a different question: after a complete
sampled world is available to an evaluator, what is the exact best immediate
Fantasy arrangement in each Hero qualification branch against that completed
opponent board?

The completed opponent board is teacher/evaluation information only. It is not
added to the sealed policy information key.

## Reuse of M4H

The M4H one-pass frontier already finds the exact best immediate board separately
for:

- Hero leaves Fantasy;
- Hero re-Fantasies.

Those branchwise immediate optima depend on the Fantasy packet, the completed
opponent board and exact scoring. They do **not** depend on whether the opponent
entered the hand in normal mode or Fantasy mode. The opponent's current mode
matters only when the terminal board is mapped to the next cross-hand state.

M4N therefore avoids duplicating the multi-million-combination search:

1. For normal/Fantasy, call M4H directly.
2. For Fantasy/Fantasy, run the same certified M4H search through a metadata-only
   asymmetric proxy.
3. Keep the exact selected boards, discards and immediate scores unchanged.
4. Replace each candidate's proxy next-state with the exact next-state calculated
   from the **actual** Fantasy/Fantasy meta-state, including the opponent's
   re-Fantasy transition.

This is an exact factorization, not an action approximation.

## Strategic use

M4N is suitable for:

- generating high-quality bounded action proposals for a sealed Fantasy policy;
- measuring how much value a reduced candidate set misses on sampled worlds;
- late-stage policy diagnostics;
- exact branchwise teacher labels.

It is **not** a legal runtime policy for a sealed Fantasy/Fantasy hand, because
its query conditions on an opponent board that is hidden at decision time.

## Gate

The M4N regression requires:

- byte/board/score/next-state parity with M4H in the already-certified asymmetric
  normal/Fantasy case;
- exact Fantasy/Fantasy next-state parity with `next_state_from_terminal_boards`;
- exact use of the real Fantasy/Fantasy continuation vector;
- no modification to M4M's policy information contract.

Passing M4N still does not solve the 32 Fantasy/Fantasy meta-states. The next
step is a bounded **own-information-only** action proposal mechanism whose missed
value is measured against this exact offline teacher.
