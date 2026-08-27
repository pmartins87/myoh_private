# M4M — Fantasy-vs-Fantasy sealed game boundary

## Why this milestone exists

The 50-state HU continuation surface contains three distinct one-hand kernels:

- 2 normal/normal states;
- 16 asymmetric normal/Fantasy states;
- **32 Fantasy/Fantasy states**.

The third family cannot be omitted from a mathematically complete Bellman solve.

## Timing authority

KKPoker's published OFC rules state that a player in Fantasy receives the full
Fantasy packet, places thirteen cards at once, and that the Fantasy cards are
not exposed until the other players have completed their hands.

Source:
`https://br.kkpoker.net/gamerules/`, section **OPEN FACE CHINESE POKER (OFC) →
3. FANTASY**.

For HU when both players are already in Fantasy, M4M interprets that published
visibility rule as a **sealed simultaneous private placement** contract: neither
player may condition the arrangement on the opponent's hidden Fantasy packet or
completed board before both have completed.

This is stronger evidence than an implementation guess, but it remains a timing
contract. A future field replay of a both-Fantasy hand should still be retained
as product-level confirmation for the Joker Ultimate UI.

## Exact game boundary

`fantasy_fantasy_kernel.py` adds:

- unique physical 14–17-card packets for both players from the 54-card
  Joker-Ultimate deck used by the certified engine;
- strict 3/5/5 + discard partition validation;
- exact current score + exact next-state continuation utility;
- zero-sum player-0/player-1 perspective conversion;
- private information keys containing the player's **own packet only**;
- exact 24-way suit canonicalization selected from that player's own information;
- suit-canonical arrangement action keys.

The regression suite changes the opponent's hidden packet while holding all own
information fixed and requires the policy information key to remain identical.

## Action-scale consequence

A raw Fantasy action is a complete 3/5/5 partition plus discards. Even before
foul/rank equivalence, the number of physical partitions is:

| packet | raw partitions |
|---:|---:|
| F14 | 1,009,008 |
| F15 | 7,567,560 |
| F16 | 40,360,320 |
| F17 | 171,531,360 |

Therefore a full tabular action vector per private packet is not a viable global
policy representation.

M4M deliberately **does not** hide this problem behind an arbitrary action
abstraction. The next milestone must build a bounded candidate/frontier or
autoregressive policy mechanism and certify its missed-best-response error
against exact sampled deviations.

## Authority

M4M certifies the game/information/terminal boundary only. It does not certify a
Fantasy/Fantasy equilibrium policy and does not close the outer relative-value
iteration by itself.
