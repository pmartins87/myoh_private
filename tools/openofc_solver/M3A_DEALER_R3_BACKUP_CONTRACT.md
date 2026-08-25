# M3a — Dealer/button R3 sampled backward-induction contract

## Decision information

At the dealer/button R3 decision, the non-dealer has already acted.  The
dealer legally knows:

- the dealer's 9 placed cards;
- the non-dealer's 11 public placed cards;
- the dealer's current 3-card R3 packet;
- the dealer's two remembered R1-R2 discards.

That is 25 unique physical cards.  The remaining 29 cards contain the
non-dealer's three hidden R1-R3 discards, both future R4 packets and 20 undealt
cards.

## Belief used by M3a-v1

The existing reachability policy chooses uniformly among legal actions and is
card-identity blind.  Conditional on the 25-card information set, the 29
unseen identities are therefore exchangeable.  One sampled world is a uniform
random partition into:

- 3 hidden non-dealer discards;
- 3 non-dealer R4 cards;
- 3 dealer R4 cards;
- 20 undealt cards.

The same sampled worlds are used for every candidate dealer R3 action.  This
common-random-number design lowers variance in action differences and prevents
one action from receiving an easier chance sample.

## Backward induction through R4

For every legal dealer R3 action and sampled world:

1. build the dealer's public 11-card board;
2. call the M2b non-dealer R4 information-set teacher using only the
   non-dealer's legal information;
3. apply each point-optimal non-dealer R4 action;
4. call the exact fully observed dealer R4 oracle with the sampled dealer
   packet;
5. retain the minimum and maximum dealer value across M2b point-optimal ties.

The last interval is important.  Choosing one convenient opponent tie would
silently insert an arbitrary policy.  M3a instead carries the complete
current-hand ambiguity forward.

## Exact and sampled components

The following parts are exact:

- KKPoker hand evaluation, royalties, foul and scoop scoring;
- physical-card uniqueness and row-local Joker semantics;
- all legal R3 and R4 actions;
- the non-dealer R4 expectimax for its explicit 26-card belief;
- the dealer R4 exhaustive terminal oracle.

The R3 chance integral is sampled because exact expansion includes millions of
hidden-history/R4-packet partitions before the nested 2,600-packet M2b trees.
Each action therefore stores its sampled lower/upper Q sums, means, observed
range and simultaneous Hoeffding interval.

`certified_unique_best_action` is emitted only if one action's lower confidence
bound is strictly above every competitor's upper bound.  If the bounds overlap,
the corpus preserves all Q intervals and emits no certified class.  No fallback
action is relabelled as mathematically optimal.

## Leakage guard

Corpus rows contain only the 25-card information set, deterministic sampling
seed, sample count and integrated action values.  They never persist the
particular opponent discards or either sampled R4 packet.  The auditor rejects
all hidden-world field names and recomputes every stored Q interval.

## Remaining work

M3a-v1 is exact at every R4 leaf and statistically controlled at the R3 chance
node under the uniform card-blind reachability belief.  It is not yet the final
long-run equilibrium because strategic self-play must replace that provisional
belief and solve Fantasy continuation EV.  The next milestone is M3b, the
non-dealer R3 information set, followed by adaptive multi-seed scaling and
policy/value distillation.
