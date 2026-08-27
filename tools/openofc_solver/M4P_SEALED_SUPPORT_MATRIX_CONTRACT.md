# M4P — sealed Fantasy support matrix and policy feature contract

## Purpose

M4O reduces each sealed Fantasy/Fantasy private packet from roughly 1 million to
171 million physical arrangements into a bounded candidate support using only
the player's own information. M4P supplies the next two pieces required before a
learned sealed policy can be trained:

1. a lossless own-information state/action feature contract for candidates; and
2. an exact zero-sum payoff matrix over two bounded supports after a complete
   sampled world is available offline.

M4P does **not** claim to solve the Fantasy/Fantasy equilibrium.

## Policy-information firewall

`fantasy_fantasy_policy_features.py` accepts only:

- acting player identity;
- public button;
- public P0/P1 Fantasy counts;
- the acting player's own 14–17-card packet;
- one arrangement drawn from that packet.

There is no opponent packet, opponent board or terminal world argument.

The state/action is first put in the same exact 24-way suit-canonical coordinate
system used by M4O. The feature vector then records, losslessly within that
coordinate system:

- player/button/Fantasy-count metadata;
- all physical cards in the own packet;
- exact top/middle/bottom membership;
- exact discarded-card membership.

State and action feature ranges are disjoint so a later sparse action-conditioned
model can reuse the deterministic generalization pattern already proven in M4C2
without reusing M4C2's normal-game feature semantics.

## Offline exact payoff matrix

`fantasy_fantasy_payoff.py` is allowed to see a complete sampled
`FantasyFantasyWorld` because it is a training/evaluation oracle, not a runtime
policy input. Given candidate supports for P0 and P1, it computes every matrix
entry with the authoritative Fantasy/Fantasy terminal utility:

    current HU points + V(exact next meta-state)

Every cell is independently checked from both player perspectives and must remain
zero-sum to numerical tolerance. Canonical action identities and the exact
continuation-vector SHA are attached to the matrix.

## Strategic diagnostic

For any mixed profile over the bounded supports, M4P reports the exact unilateral
deviation gain available **inside those supports** to each player. The sum is a
support-restricted deviation diagnostic.

This quantity is deliberately not called full exploitability. There are two
separate approximation budgets:

1. **support loss** — actions omitted by M4O, measured against the unrestricted
   exact M4N teacher on held-out worlds;
2. **policy loss inside support** — measured by M4P's exact support-restricted
   unilateral deviation gains.

A future promotion certificate must account for both rather than hiding one
inside the other.

## Gate

The M4P regression requires:

- policy API has no opponent-card input;
- exact 24-way suit invariance of policy state/action features;
- distinct candidate arrangements remain distinguishable;
- exact payoff-matrix parity with the authoritative terminal utility;
- exact zero-sum perspective parity;
- global suit invariance of matrix values and canonical action identities;
- non-negative support-restricted deviation gains.

## Next milestone

M4Q should train a bounded generalizing sealed action-value/advantage model on
M4P examples. Initial targets may use an explicitly labelled bootstrap opponent
mixture, but no bootstrap policy may be promoted as an equilibrium. Later
self-play/regret iterations must be evaluated with the two-budget decomposition
above.
