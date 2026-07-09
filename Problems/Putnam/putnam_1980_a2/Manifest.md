---
problem: Putnam.putnam_1980_a2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1980_a2 — imported from PutnamBench

Original theorem: `putnam_1980_a2` (Putnam 1980 A2).

## Statement

Let $r$ and $s$ be positive integers. Derive a formula for the number of ordered quadruples $(a,b,c,d)$ of positive integers such that $3^r \cdot 7^s=\text{lcm}[a,b,c]=\text{lcm}[a,b,d]=\text{lcm}[a,c,d]=\text{lcm}[b,c,d]$. The answer should be a function of $r$ and $s$. (Note that $\text{lcm}[x,y,z]$ denotes the least common multiple of $x,y,z$.)

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
