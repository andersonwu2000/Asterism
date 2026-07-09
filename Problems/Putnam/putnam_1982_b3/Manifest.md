---
problem: Putnam.putnam_1982_b3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1982_b3 — imported from PutnamBench

Original theorem: `putnam_1982_b3` (Putnam 1982 B3).

## Statement

Let $p_n$ denote the probability that $c + d$ will be a perfect square if $c$ and $d$ are selected independently and uniformly at random from $\{1, 2, 3, \dots, n\}$. Express $\lim_{n \rightarrow \infty} p_n \sqrt{n}$ in the form $r(\sqrt{s} - t)$ for integers $s$ and $t$ and rational $r$.

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
