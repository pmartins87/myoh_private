# M3a-scale corpus and convergence contract

M3a-scale turns the dealer/button R3 backup kernel into a reproducible training
data pipeline.  It does not change the live OpenHoldem policy by itself.

## Shard identity and safe resume

`run_r3_dealer_shards.py` divides every requested seed into contiguous deal-id
ranges.  A shard is resumable only when all of the following still match:

- seed, seed index, deal range and record count;
- hidden-world samples per action and confidence delta;
- corpus and manifest schema versions;
- SHA-256 of the JSONL file;
- independently recomputed audit result.

Changing the sample budget or confidence delta therefore cannot silently reuse
an incompatible label.  Every attempted R3 state is retained, including flat
states: a true strategic equivalence is information and must not be filtered
merely because it is unhelpful for a single-class classifier.

## Multi-seed coverage

Repeating `--seed` generates independent reachability states and independent
hidden-world streams.  The manifest key is `(base_seed, deal_id)`, so identical
deal ids from different seeds remain distinct and auditable.  The aggregate
auditor proves contiguous coverage independently for every seed and rejects
duplicate keys, missing ranges, modified shards and hidden-world leakage.

## N versus kN convergence

`audit_r3_convergence.py` takes the same stored information set and recomputes
it with the same deterministic hidden-world seed at `k*N` samples.  Python's
sampler makes the original N worlds an exact prefix of the expanded stream.
The comparison therefore measures additional-sample stability without changing
the cards or belief model.

The report records:

- robust-best set exact stability and overlap;
- regret of the N-sample selected set when evaluated at kN;
- maximum drift of lower/upper empirical means;
- certificate retention and new certificates;
- the Hoeffding margin contraction, exactly `1/sqrt(k)`.

Optional thresholds make the command fail closed.  No default numerical
threshold is claimed to prove convergence: the Ryzen scale run must establish
empirical tolerances across many seeds before M3a is distilled into the live
policy.

## Mathematical scope

R4 leaves and rule evaluation remain exact under the documented v1 belief.
The R3 hidden-world integral remains sampled, and the reachability distribution
remains card-blind rather than an equilibrium policy.  Consequently this is a
certified sampled-backup corpus, not yet a proof of perfect full-game play.
