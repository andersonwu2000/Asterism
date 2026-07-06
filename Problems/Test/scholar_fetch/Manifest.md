---
problem: Test.scholar_fetch
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
paper: 1d60ef74ee5d
---

# Test.scholar_fetch

## Statement

The bound paper's §3.3 (polyhedra) leans on the cited companion work
by Roeder–Hubbard–Dunbar on Andreev's theorem. We will eventually need
that companion in the workspace. Independently, formalize one small
warm-up fact about the paper's §2.8 monodromy matrices.

### Deliverables

`MarkDeliverable` the claim; then `Ingest`:

- `sl2z_neg_one_sq` — in `Matrix.SpecialLinearGroup (Fin 2) ℤ`,
  `(-1 : SL(2,ℤ))^2 = 1`.

## Strategic notes

Before Ingest, make sure the Roeder–Hubbard–Dunbar companion paper
(cited in the bound paper's §3.3) is fetched and bound to this problem
— use `FetchPaper` with the citation; a Scholar agent resolves it.
