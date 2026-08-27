# M4C — strategic generalization trigger and lossless visible feature contract

## Why exact tabular MCCFR is no longer the production scaling plan

The M4 feasibility run supplied an important negative result before we spent Ryzen days on the wrong representation. At 300 iterations / 600 episodes, the suit-canonical exact tabular solver touched 6,000 decision nodes but created 5,997 distinct information sets. Only three node touches were reuse, the regret-update reuse fraction was about 0.00033, and the maximum observed regret visits to one information set was 2.

The same report projected about 19,990 information sets at 1k iterations, 199,900 at 10k, 1,999,000 at 100k and 19,990,000 at 1M if the measured growth remained approximately linear. Those projections are engineering diagnostics, not proofs; the decisive observation is that the early exact table is learning almost one new key per decision instead of repeatedly improving old regrets.

More CPU does not fix that representation problem. Suit symmetry is exact and remains mandatory, but the physical-card/public-history game is too large for a raw exact table to be our practical global learner.

## Project response

The unabstracted tabular solver remains an oracle and correctness harness. Production-scale strategic learning now adds **function generalization** only after exhausting the exact reductions already implemented. This is an approximation and therefore does not inherit an exactness label. Its loss must later be bounded against exact late-round teachers, unabstracted sampled subgames and best-response diagnostics.

The first requirement is that the model input itself must not throw away strategic information. `strategic_feature_encoder.py` therefore converts the existing exact 24-way-suit canonical information key plus one legal action into a fixed sparse feature vector while preserving:

- actor/relative position and round;
- both public boards;
- the acting player's private current packet;
- the acting player's own private discards;
- the full public placement history by round, player, physical card and row;
- the complete candidate action, including the private discard choice;
- physical distinction of both Jokers;
- all 232 opening actions.

It reads only the already information-safe canonical key, so opponent hidden packets, opponent private discards, future cards and determinization identifiers cannot enter the model input.

## Feature layout v1

The sparse binary vector has 2,276 dimensions:

- bias: 1;
- acting player: 2;
- round: 5;
- self board: 3 x 54;
- opponent board: 3 x 54;
- own discards: 54;
- current incoming packet: 54;
- public history: 5 rounds x 2 players x 3 rows x 54 cards;
- candidate action: 4 destinations (top/middle/bottom/discard) x 54 cards.

This encoder is intentionally lossless relative to the strategic variables represented by the current suit-canonical key. Generalization happens in the learned regret/value function, not by silently deleting public-history or card-identity information at the input boundary.

## Next implementation layer

M4C continues with an action-conditioned regret/advantage approximator trained from MCCFR trajectories, with bounded replay memory and deterministic checkpoints. Exact R4/R3 teachers will be used as supervised calibration anchors. The continuation-coupled M4B objective remains the long-horizon target, so a learned model is not promoted merely for fitting current-hand points.

No field test is a promotion gate here. The next field test stays deferred until the strategic model, continuation objective and production integration are ready.
