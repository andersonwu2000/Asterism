---
problem: Test.sl2z_monodromy
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
paper: 1d60ef74ee5d
---

# Test.sl2z_monodromy

## Statement

The bound paper classifies torus bundles by the trace of the monodromy
matrix (somewhere around §2.8 / §3.2). Formalize the algebraic
dichotomy behind that classification for `A ∈ SL(2,ℤ)`: small trace
means finite order, large trace means infinite order. Check the paper
for what small/large mean exactly and which side the boundary cases
belong to — the boundary itself is out of scope.

### Deliverables

`MarkDeliverable` each; then `Ingest`:

- `sl2z_small_trace_finite_order`
- `sl2z_large_trace_infinite_order`

Do NOT introduce axioms or `sorry`-bearing shortcuts.
