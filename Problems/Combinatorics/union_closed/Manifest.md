---
problem: Combinatorics.union_closed
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Combinatorics.union_closed — the union-closed sets conjecture (Frankl)

## Statement

Prove the union-closed sets conjecture:

Let F be a finite family of finite sets that is closed under union and
contains at least one nonempty set. Then there exists an element x that
belongs to at least half of the members of F.

The formal statement is pinned in `Root.lean` (`theorem main`).

(This is the stress test required for framework development. Keep an open mind.)

## Strategic notes

Attempt to prove the original conjecture. Use the framework to verify your own
thinking and conjectures — do not stay within known results. Judge every arc by
the distance it removes.

Survey the literature before committing to a line of attack — `FetchPaper` is
available.

Partial results with kernel-checked content — improved constants, new structural
classes settled, sharpened lemmas — are valuable deliverables in their own right;
mark them as you go rather than holding everything for the endgame.
