---
problem: Topology.simple_loop_conjecture
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Topology.simple_loop_conjecture

## Statement

Prove Conjecture 2 (Simple Loop Conjecture) of the paper [p.5]:

Let f : S → M be a map from an orientable surface to a 3-manifold.
If f∗ : π₁(S) → π₁(M) is not injective, there is an element in
ker f∗ that is represented by a simple (that is, embedded) loop.

(This is the stress test required for framework development. Keep an open mind.)

## Strategic notes

Attempt to prove the original conjecture. Use the framework to verify your own
thinking and conjectures — do not stay within known results. Judge every arc by
the distance it removes.

Survey the literature before committing to a line of attack — `FetchPaper` is
available.

The paper-fetch whitelist now includes publisher open archives (AMS / Project
Euclid / MSP); a paper previously recorded as unfetchable may now resolve.