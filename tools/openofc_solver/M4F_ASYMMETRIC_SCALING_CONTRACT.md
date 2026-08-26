# M4F — practical scaling for the normal-vs-Fantasy kernel

## Goal

M4E defined the exact asymmetric hand model but deliberately did not pretend that repeatedly solving millions of Fantasy mask pairs inside training was practical. M4F adds two lossless reductions before any approximation is introduced.

## 1. Policy-side 24-way suit isomorphism

`normal_fantasy_symmetry.py` canonicalizes the normal player's visible information over all global suit permutations.

The canonical map is selected from:

- meta-state/button and Fantasy size;
- normal player's board;
- normal player's remembered discards;
- current normal incoming packet.

The hidden Fantasy packet is never consulted. Consequently suit reduction cannot leak hidden cards into the normal policy. Legal actions are transformed by the same map, preserving the complete action surface.

This is an exact game automorphism, not an abstraction.

## 2. Oracle-side suit-canonical Fantasy frontier cache

The terminal oracle is allowed to know the hidden Fantasy packet because it is evaluating a sampled complete world, not constructing a player's information state.

`fantasy_frontier_cache.py` canonicalizes `(Fantasy packet, completed normal board, variant)` over the same 24 suit permutations and stores only:

- best immediate points among no-re-Fantasy arrangements, if reachable;
- best immediate points among re-Fantasy arrangements, if reachable.

Those two values are exact outputs of M4D. A new continuation vector is then evaluated with constant-time arithmetic; no 14–17-card search is repeated.

Suit-isomorphic complete worlds share one exact cache entry.

## Security/information boundary

The two canonicalizations have intentionally different information privileges:

- **policy canonicalization**: visible normal-player information only;
- **terminal oracle cache**: complete sampled world, including hidden Fantasy packet.

The terminal cache key must never be passed to the policy model. Tests keep those APIs separate.

## Remaining practical bottleneck

Exact cache misses are still expensive, especially F16/F17. Cache reuse across random complete worlds may be limited. The next feasibility probe must measure hit rate and exact-frontier throughput on realistic sampled trajectories before we decide whether to:

1. keep exact on-demand search;
2. accelerate the frontier builder in C++/parallel CPU;
3. distill the two exact immediate frontier values into a bounded terminal-value model with held-out exact error bounds.

The decision is empirical. We will not commit the Ryzen to a representation whose measured cache/reuse economics are poor.
