---
problem: Putnam.putnam_2025_a3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_a3 — imported from PutnamBench

Original theorem: `putnam_2025_a3` (Putnam 2025 A3).

## Statement

Alice and Bob play a game with a string of $n$ digits, each of which is restricted
to be 0, 1, or 2. Initially all the digits are 0. A legal move is to add or subtract 1
from one digit to create a new string that has not appeared before. A player with no
legal move loses, and the other player wins. Alice goes first, and the players alternate
moves. For each $n \ge 1$, determine which player has a strategy that guarantees winning.

The formal statement is pinned in `Root.lean` (`theorem main`).
The `_solution` abbrev in `Defs.lean` carries the OFFICIAL
answer (upstream ships it as a comment; this matches the
standard solutions-replaced evaluation protocol — the task
is proving, not answer-finding).

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
