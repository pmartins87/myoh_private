# M1b rule contract — Joker substitution semantics

Status: **candidate contract pending strict CI parity**.

## Source-backed rules

The KKPoker in-client `Advanced play` rule captured for this project states:

> The two Jokers can represent any other playing card to form the strongest hand, as long as it is not fouled.

The KKPoker in-client `Scoring` rule captured for this project states that the score and royalties of **each row are calculated separately**.

The current official KKPoker OFC rules page also says that the three poker hands are compared row-by-row and that OFC uses the traditional poker hand rankings used in games such as NLH and PLO. Its listed ranking has Royal Flush through High Card and does not define Five of a Kind.

## Interpretation adopted by the solver

These source rules imply two different notions of uniqueness which must not be conflated:

1. **Physical dealt cards are globally unique.** The 13 regular cards actually dealt onto one board cannot contain the same exact card twice.
2. **Joker substitution identity is row-local.** A Joker in Middle may represent `7c` even if the physical `7c` is visible in Top or Bottom, because KKPoker evaluates/scorers each row separately.
3. **Inside one row, represented playing cards must still form a legal traditional poker hand.** A Joker cannot become the exact `Ah` when `Ah` is already physically present in that same row, and two Jokers cannot both become the same exact `Ah`. They may share a rank when using different suits, e.g. two Jokers plus one physical seven may legally form trips sevens.
4. **Strongest non-fouled board.** Resolve Bottom to its strongest legal row, then Middle to its strongest legal rank not exceeding Bottom, then Top to its strongest legal rank not exceeding Middle. Stronger Bottom/Middle choices only relax the ranking constraint for the row above, so this greedy order gives the lexicographically strongest legal board.

The within-row exact-card uniqueness rule is an interpretation of `traditional poker hand` semantics rather than an explicit KKPoker sentence about duplicate Joker identity. It is fail-closed and prevents impossible constructs such as an `Ah Ah 9h 8h 5h` "flush". If direct KKPoker evidence ever contradicts it, this contract must be revised before training data are regenerated.

## Regression examples

### Cross-row reuse — allowed

```text
Top:     7s 5h 3s
Middle:  JK1 3h 6h JK2 Jc
Bottom:  9c 7d 2c 7h Ah
```

Expected Middle: pair of sevens. The two Jokers may use two distinct seven identities even though sevens are physically visible in other rows.

### Same-row exact duplicate — forbidden

```text
Top:     2c 3d 4s
Middle:  Ah 9h 8h 5h JK1
Bottom:  9c Tc Jc Qc Kc
```

Expected Middle: `A-K-9-8-5` flush. The Joker may not create a second `Ah` in the same five-card hand.

### Two Jokers in one row — distinct playing cards

```text
Top:     2c 3d 4s
Middle:  Ah 9h 8h JK1 JK2
Bottom:  9c Tc Jc Qc Kc
```

Expected Middle: `A-K-Q-9-8` flush, using two different heart cards.

## Training gate

No long M2+ corpus generation is certified until:

- targeted tests above pass;
- Python exact engine and materialized C++ evaluator agree on a deterministic broad Joker corpus;
- the strict Joker parity gate is GREEN.
