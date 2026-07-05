---
problem: Topology.sphere_homology
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Topology.sphere_homology — singular homology of the n-sphere

## Statement

Compute the singular homology of the spheres, with coefficients in an
arbitrary ring `R`. The Mayer–Vietoris long exact sequence is already in the
Library (`Library.AlgebraicTopology.MayerVietoris.*`) — cite it, do not
rebuild it.

For `n ≥ 1`: `H_k(S^n; R) ≅ R` for `k = 0` and `k = n`, and `H_k(S^n; R) ≅ 0`
for all other `k`. Here `S^n` is `TopCat.sphere n` and `H_k` is mathlib's
singular homology (`AlgebraicTopology.singularHomologyFunctor`).

### Deliverables

- `sphere_homology_top` — `H_n(S^n; R) ≅ R` (n ≥ 1)
- `sphere_homology_zero` — `H_0(S^n; R) ≅ R`
- `sphere_homology_eq_zero_of_ne` — `H_k(S^n; R) ≅ 0` for `k ∉ {0, n}` (n ≥ 1)

If a genuine wall is hit, stalling is diagnostic data — do NOT introduce
axioms or `sorry`-bearing shortcuts.
