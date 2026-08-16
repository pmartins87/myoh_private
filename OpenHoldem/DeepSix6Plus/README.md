# DeepSix6Plus read-only boundary

This directory is the first isolated 6+ / Short Deck observation layer in the
`deepsix_6plus` branch.

Rules for this boundary:

- read the already-scraped OpenHoldem table state only;
- do **not** call `prwin`, 1326/2652, legacy hand evaluators or blind/position
  engines for strategic meaning;
- do **not** click, type, size a bet or trigger the autoplayer;
- preserve raw scraper facts separately from strategic inference;
- reject known cards below rank 6 when validating a snapshot as Short Deck;
- allow an unknown Hero chair in the raw snapshot so observer-mode frames can
  be recorded without being misclassified as playable decisions.

`RawTableSnapshot` deliberately contains raw seats, cards, balances, current
bets and pot slots. It does **not** infer folds, action history, committed-total,
legal raise bounds or terminality. Those belong to the versioned DeepSix state
reconstructor and will be derived from successive snapshots with replay tests.

The raw structural validator is kept separate from the MFC/OpenHoldem capture
code so it can be compiled independently in CI. `RawTableSnapshotJson` emits a
deterministic audit representation; scraped money remains raw `double` evidence
and is serialized as round-trip decimal **strings**, not promoted to strategic
money. Exact integer-unit conversion happens later under a versioned table/stake
configuration.
