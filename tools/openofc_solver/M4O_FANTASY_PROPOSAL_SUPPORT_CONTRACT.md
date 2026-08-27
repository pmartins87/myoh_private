# M4O — bounded own-information Fantasy action support

## Problem

M4M measured the raw complete-arrangement action space at roughly 1.0 million
(F14) through 171.5 million (F17) physical partitions per private packet. A
sealed Fantasy/Fantasy policy cannot carry a dense probability vector over that
space.

M4O introduces a **proposal support** rather than pretending the action space is
small.

## Information contract

Proposal generation accepts only:

- the player's own Fantasy packet;
- public HU meta-state (button and both public Fantasy counts);
- the current 50-state continuation vector;
- deterministic engineering parameters/seed.

There is no argument for the actual hidden opponent packet or actual completed
opponent board.

Before any synthetic sampling, the own packet is put into an exact 24-way suit
canonical coordinate system. Synthetic worlds and M4N teacher calls are made in
that canonical coordinate and selected arrangements are mapped back to the
physical suits. Therefore suit-isomorphic private packets generate the same
canonical action support.

## Proposal construction

For each requested synthetic world:

1. sample an opponent Fantasy packet from the remaining physical deck,
   conditioned on the known public opponent Fantasy count;
2. produce a bounded random non-foul completed opponent board from that
   synthetic packet;
3. run the exact M4N counterfactual poker teacher against that synthetic board;
4. retain both reachable Hero branch optima (leave Fantasy / re-Fantasy);
5. deduplicate arrangements in canonical suit coordinates;
6. rank repeated proposals deterministically and cap the support.

This mechanism is intentionally expensive and offline. It is a research bridge
for discovering and measuring useful action support; it is not the final runtime
Fantasy policy generator.

## Exact quality metric

`evaluate_proposal_support` takes a held-out completed opponent board only in the
evaluation layer. It compares:

- unrestricted exact M4N teacher utility;
- the best exact utility achievable by any arrangement inside the bounded M4O
  support.

Their non-negative difference is the **support gap**.

This is stricter and more informative than checking whether a particular label
appears in the candidate set. It measures the points-plus-continuation value
actually lost by the action reduction on that complete evaluation world.

The support gap is still not sealed-policy regret: evaluation is allowed to pick
the best support action after seeing the held-out opponent board. M4O certifies
only action-support coverage. A later sealed policy must learn how to mix/select
inside the support from own information alone.

## Promotion rule

No `synthetic_worlds`, support-size or gap threshold is frozen from smoke tests.
Before M4O can constrain the production action space we require Ryzen-scale,
multiseed held-out measurements across:

- F14/F15/F16/F17 for both players;
- 0/1/2 Joker own packets;
- multiple opponent Fantasy-count pairings;
- later, opponent boards sampled from the learned sealed policy rather than only
  the bootstrap synthetic-board generator.

Exact M4N remains the authority for measuring missed support.
