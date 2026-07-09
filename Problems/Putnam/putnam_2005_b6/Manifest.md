---
problem: Putnam.putnam_2005_b6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2005_b6 — imported from PutnamBench

Original theorem: `putnam_2005_b6` (Putnam 2005 B6).

## Statement

Let $S_n$ denote the set of all permutations of the numbers $1,2,\dots,n$. For $\pi \in S_n$, let $\sigma(\pi)=1$ if $\pi$ is an even permutation and $\sigma(\pi)=-1$ if $\pi$ is an odd permutation. Also, let $\nu(\pi)$ denote the number of fixed points of $\pi$. Show that $\sum_{\pi \in S_n} \frac{\sigma(\pi)}{\nu(\pi)+1}=(-1)^{n+1}\frac{n}{n+1}$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
