---
problem: Test.sl2z_parabolic
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
paper: 1d60ef74ee5d
---

# Test.sl2z_parabolic

## Statement

A sibling problem (`Test.sl2z_monodromy`) already covers the two open
sides of the paper's monodromy trace classification. This one is the
boundary that was left out: for `A ∈ SL(2,ℤ)` with trace on the
boundary, decide the order dichotomy. The paper says which geometry
this case carries and which matrices are the exceptions — check it.

### Deliverables

`MarkDeliverable` each; then `Ingest`:

- `sl2z_parabolic_infinite_order`

Do NOT introduce axioms or `sorry`-bearing shortcuts.
