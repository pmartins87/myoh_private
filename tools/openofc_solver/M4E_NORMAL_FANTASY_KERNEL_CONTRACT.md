# M4E — asymmetric normal-vs-Fantasy HU hand kernel

## Scope

M4E materializes the one-hand game when exactly one HU player is in Fantasy and the other plays the five normal OFC rounds.

The timing model is explicit: the Fantasy player keeps the arrangement unconfirmed while the normal player completes the board, then chooses the exact delayed best response. This behavior is supported by the captured KKPoker field sequence, but remains a named timing contract rather than an undocumented assumption.

## Information structure

The normal player sees:

- the current meta-state/button;
- own public board;
- own remembered private discards;
- current private incoming packet;
- the opponent's Fantasy size (14/15/16/17).

The hidden Fantasy packet never enters the normal player's information key. Because the Fantasy player emits no public placement before normal completion under this timing model, there is no opponent action signal to update the normal player's belief. Own board + remembered discards contains all previously observed normal cards, so the compressed state is Markov for the normal player's decision problem.

A complete sampled hand contains `FantasyCount + 17` unique physical cards: the hidden Fantasy packet plus the normal player's 5-card opening and four 3-card packets.

## Terminal utility

After the normal board is complete, M4E calls the exact M4D two-branch Fantasy frontier. The frontier is evaluated under the supplied 50-state continuation vector. The result is from the Fantasy player's perspective; the normal player's utility is its zero-sum negative.

Authority: `EXACT_NORMAL_FANTASY_HAND_MODEL_GIVEN_V_AND_DELAYED_TIMING`.

This is an exact game model boundary, not yet a solved normal-player policy.

## Practical consequence

The asymmetric kernel is much simpler strategically than normal-vs-normal under delayed Fantasy timing:

- only the normal player takes sequential decisions before terminal;
- the Fantasy packet remains hidden chance rather than an acting/signalling opponent;
- the terminal opponent response is exact;
- the difficult remaining task is learning/planning the normal player's policy under hidden Fantasy cards and future packets.

The raw exact Fantasy frontier remains too expensive to regenerate at every training trajectory, especially for F16/F17. The production learner therefore needs frontier caching/distillation or a faster exact implementation, with held-out exact-frontier error measured before promotion.

## Next gate

M4F will add exact 24-way suit canonicalization for the asymmetric normal information state and a bounded terminal-frontier teacher/cache interface. Only after that representation is measured do we choose the training algorithm, avoiding another tabular state explosion.
