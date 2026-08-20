# OpenOFC final AI roadmap

## Objective

Build the strongest practical Joker Ultimate OFC policy supported by the measured KKPoker simulator contract, while keeping perception/execution independent from strategy. The live runtime should be able to swap `COFCBaselinePolicy` for a stronger policy without changing scraping, canonical state, turn planning or mouse execution.

## Stage S0 — rules-exact evaluator

Freeze and test the exact game objective:

- row ordering / foul legality;
- top, middle and bottom royalties;
- row wins/losses and scoop bonus;
- physical Joker semantics;
- normal Fantasy entry (QQ/KK/AA/trips as measured for Joker Ultimate);
- Ultimate re-fantasy condition and retained Fantasy card count;
- continuation value across chained Fantasy hands.

Every later learner/searcher must optimize the same terminal point function.

## Stage S1 — headless simulator

Create a UI-free deterministic game engine with seeded chance. It must generate normal R0..R4 and Fantasy, expose public/private observations at the same information sets as KKPoker, and reproduce scoring exactly. The simulator becomes the training environment and is benchmarked in states/second before choosing training budgets.

## Stage S2 — strong non-trained search baseline

Normal OFC has small action branching but large chance branching. Use sampled expectimax / information-set Monte Carlo rollouts over remaining cards and opponent hidden cards, conditioned on all public history. Keep a deterministic heuristic/value evaluator at rollout leaves.

Fantasy is different: all Hero cards are known. Solve the 3/5/5 partition combinatorially with legality, royalties, current opponent score and re-fantasy continuation value. It does not need neural training for the core arrangement problem.

## Stage S3 — search oracle + self-play corpus

Run large parallel self-play batches. For each decision store:

- canonical information state;
- legal actions;
- sampled-search action values;
- chosen policy distribution;
- terminal score and Fantasy continuation outcome.

This creates supervised targets for a compact policy/value model and allows regression testing against the search oracle.

## Stage S4 — equilibrium-oriented policy/value model

Train a compact network or other function approximator for policy and counterfactual/value estimates. Candidate training families include sampled CFR/Deep-CFR-style updates and search-distillation/self-play. Full tabular CFR is not appropriate for the raw state space.

Selection is empirical: compare held-out self-play exploitability proxies, head-to-head score, calibration and inference latency. The architecture is not frozen before the headless simulator benchmark.

## Stage S5 — hybrid live policy

Live decision:

1. compact base policy/value gives an immediate candidate;
2. bounded sampled search refines it with the current remaining-card belief;
3. dealer-side provisional organization may use an early search result;
4. once opponent final public placement appears, re-search with the new information and adjust only if EV changes enough.

This matches the simultaneous-dealer runtime already implemented.

## Stage S6 — opponent model and exploitation

Use `OFCHandAudit` / `OFCReconstructedActions` only when reconstruction is exact. Estimate player-specific conditional action distributions with confidence/sample thresholds. The opponent model changes the sampled opponent policy and hidden-card inference; it does not overwrite the base strategy blindly.

Maintain two outputs:

- robust/base EV versus the reference population/self-play policy;
- exploit EV versus the player-specific posterior.

Exploit only when the estimated gain exceeds uncertainty and safety thresholds.

## Compute strategy

Do not commit to a wall-clock training promise before S1 benchmark. Raw action branching is modest (normal opening <=232 capacity-valid labelled assignments; later rounds <=27 raw discard/placement choices), while chance branching is the expensive dimension. Fantasy raw partitions grow from about 1.0M at 14 cards to 171.5M at 17 cards before pruning/caching, but this is an exact combinatorial optimization problem rather than a training problem.

Use CPU parallelism first for simulation/search. A GPU becomes useful when a neural policy/value model is introduced, but is not required for S0-S3 or exact Fantasy. Training budgets should grow through measured ladders with held-out evaluation rather than one monolithic run.

## Stop/go gates

1. Runtime/perception field-stable normal + Fantasy.
2. Rules-exact evaluator passes exhaustive targeted tests.
3. Headless simulator reproduces known hands and reaches target throughput.
4. Search baseline beats v5.3 smart heuristic by a statistically meaningful margin.
5. Learned model matches search oracle on held-out decisions and beats it or approaches it with much lower latency.
6. Opponent exploitation improves score out-of-sample without degrading robust baseline beyond the configured bound.
