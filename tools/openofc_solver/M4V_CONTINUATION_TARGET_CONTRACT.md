# M4V — continuation-linear sealed action targets

## Purpose

M4U proved that the existing M4S/M4T certificate is tied to one continuation
vector and added exact cell-level factorization:

`payoff(action0, action1) = immediate + V(next_state)`.

M4V pushes the same exact factorization through an **explicit frozen opponent
support mixture**. For every own candidate action it stores:

- expected immediate current-hand utility;
- a sparse signed distribution over exact next HU continuation states.

The resulting target is a linear functional:

`Q_a(V) = immediate_a + Σ_s c[a,s] V(s)`.

For player 0 the coefficients sum to `+1`. For player 1 they sum to `-1`,
preserving the repository's convention that the 50-state continuation vector is
always stored from persistent player-0 perspective.

## Why this matters

M4Q/M4R currently learn a scalar Q target produced under one particular
continuation vector. The scalar becomes stale as soon as the outer Bellman
iteration changes `V`.

M4V shows that this staleness is avoidable at the exact target layer. For a
fixed support and fixed opponent mixture, the expensive complete-world scoring
can be performed once and Q can then be rematerialized for any new `V` with
only a sparse dot product.

This is the same structural idea that made M4D practical, now applied to sealed
Fantasy/Fantasy strategic action values.

## Hidden-information firewall

The factorization is an **offline target representation**. It is derived from the
complete M4P sampled world, exactly where hidden-world information is already
permitted for training labels.

It is not a runtime policy feature and does not expose opponent cards to
`policy_for_private_support`.

A later generalizer must learn the continuation-relevant outcome quantities from
own information only.

## Exact regression

The M4V gate:

1. builds one exact M4U factorized support matrix;
2. freezes non-uniform opponent mixtures;
3. creates continuation-linear targets once;
4. evaluates them under multiple materially different 50-state vectors;
5. independently rematerializes ordinary M4P matrices for each vector;
6. calls the existing M4Q bootstrap target generator;
7. requires every P0 and P1 action value to agree to `1e-12`.

Thus M4V adds no new poker-scoring authority.

## Remaining dependency

M4V does **not** solve two remaining issues:

- the M4O candidate support itself was selected under an anchor continuation
  vector and may miss a newly optimal action under another `V`;
- the opponent policy can change as `V` changes, so the frozen-mixture
  coefficients must be recomputed during self-play.

The second operation is cheap once the factorized matrix exists. The first still
requires a support-robustness proof.

## Next milestone

M4W should replace scalar continuation-anchor Q generalization with an
own-information outcome model that predicts the components M4V needs:

- expected immediate score;
- next-state mass over the reachable continuation slice.

Then the policy can reconstruct Q under the current Bellman vector without
putting hidden opponent cards into inference. In parallel, support generation
must be audited over a declared family of continuation vectors rather than only
one anchor.
