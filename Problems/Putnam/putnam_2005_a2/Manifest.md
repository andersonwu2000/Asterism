---
problem: Putnam.putnam_2005_a2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2005_a2 — imported from PutnamBench

Original theorem: `putnam_2005_a2` (Putnam 2005 A2).

## Statement

Let $\mathbf{S} = \{(a,b) | a = 1, 2, \dots,n, b = 1,2,3\}$.
A \emph{rook tour} of $\mathbf{S}$ is a polygonal path made up of line segments connecting points $p_1, p_2, \dots, p_{3n}$ in sequence such that
\begin{enumerate}
\item[(i)] $p_i \in \mathbf{S}$,
\item[(ii)] $p_i$ and $p_{i+1}$ are a unit distance apart, for
$1 \leq i <3n$,
\item[(iii)] for each $p \in \mathbf{S}$ there is a unique $i$ such that
$p_i = p$.
\end{enumerate}
How many rook tours are there that begin at $(1,1)$
and end at $(n,1)$?

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
