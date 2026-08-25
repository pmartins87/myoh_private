# M2b — Non-dealer R4 information-set contract

## Why dealer R4 and non-dealer R4 are different

In heads-up KKPoker OFC, the non-dealer acts first and the dealer/button acts second.

For **dealer/button R4**, the opponent has already placed their last two cards and discarded one. The opponent final 13-card board is public. `teacher_search.solve_r4_exact` can therefore enumerate Hero's legal actions against a fully observed terminal opponent board without looking into hidden future information.

For **non-dealer R4**, Hero must act while the dealer's current three-card packet is still hidden. Labelling this state with the dealer's actually dealt packet would be hindsight leakage. M2b therefore represents a genuine information set and integrates over the hidden packet.

## Information visible to Hero

At the non-dealer R4 decision under the current normal-game model, Hero knows:

- Hero's 11 placed cards;
- opponent's 11 public placed cards;
- Hero's current 3-card R4 packet;
- Hero's own three earlier discarded cards from R1-R3.

That is 28 distinct physical cards from the 54-card KKPoker deck (52 standard cards + two distinct Jokers). Therefore 26 physical cards are unseen by Hero.

Opponent previous discards are **not** included. They are hidden during live play and only become passive history evidence if the result UI later reveals them. The runtime opponent-history collector intentionally treats those identities as post-hand evidence, not as an action gate.

## Why the M2 reachability belief is uniform over 26 choose 3

M2 currently uses `UNIFORM_LEGAL_REACHABILITY_ONLY_NOT_TEACHER` for R0-R3. It chooses uniformly among legal placement/discard actions only to sample reachable states. The action generator depends on:

- row capacities;
- incoming indices;
- round placement/discard cardinality.

It does **not** inspect card rank, suit or Joker identity when deciding which legal action exists. For any fixed row-capacity shape, the three possible incoming discard indices have equal action multiplicity. `test_r4_nondealer.py` checks that symmetry over every reachable capacity shape for R1-R4.

Consequently, conditional on the 28 cards visible/remembered by Hero, the hidden physical card identities remain exchangeable under this reachability process. The dealer's R4 packet is exactly uniform over the three-card subsets of the 26 unseen cards:

`C(26, 3) = 2600`.

This statement is deliberately narrow: it is true for the current **uniform legal reachability sampler**. It is not a claim that a strategic opponent or later self-play policy induces the same posterior distribution.

## M2b-v1 exact current-hand expectimax

`teacher_search_nondealer.solve_r4_nondealer_uniform_belief` performs the following calculation for each legal Hero R4 action:

1. build Hero's final board;
2. enumerate all 2,600 possible hidden dealer packets with equal probability;
3. for each packet, enumerate every legal dealer R4 response after seeing Hero's final board;
4. score every terminal pairing using the certified KKPoker current-hand point evaluator;
5. choose the dealer response that minimizes Hero's current-hand score (zero-sum current-hand best response);
6. sum the resulting score across all packets.

The resulting Q value is stored exactly as an integer numerator with common denominator 2,600. No floating-point label is required.

## What is exact, and what is not yet final strategy

M2b-v1 is exact for **current-hand points under the explicit M2 uniform-unseen belief and a current-hand best-responding dealer**.

It is not yet the final long-run OFC solution for two reasons:

1. a strategic opponent policy will make earlier hidden-action histories informative, so later self-play must replace the uniform reachability posterior with the policy-induced belief;
2. entering/re-entering Fantasy has continuation value beyond current-hand points. That continuation EV must be learned/solved, not replaced by an arbitrary bonus.

The current teacher therefore stores Fantasy qualification metadata separately. It must never silently convert `14/15/16/17 Fantasy cards` into fabricated point values.

## Leakage rule

The corpus generator deliberately stops before reading the particular shuffled-world dealer R4 packet into the training record. A row stores only the information set and the integrated Q vector. The independent auditor rejects fields such as `opponent_r4_packet`, `actual_opponent_packet`, `hidden_opponent_packet`, or `opponent_incoming`.

This keeps the distinction between a simulator's omniscient state and the player's legal information set explicit and machine-checkable.
