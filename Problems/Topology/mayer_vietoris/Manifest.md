---
problem: Topology.mayer_vietoris
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Topology.mayer_vietoris — Mayer–Vietoris long exact sequence in singular homology

## Statement
True

## Strategic notes

**This is RUN 1 of a multi-run program** to compute the singular homology of
spheres `H_k(Sⁿ)`. Run 1 builds the reusable engine: the **Mayer–Vietoris long
exact sequence** for singular homology of an open cover. Later runs use it for
the sphere reduction `H̃_k(Sⁿ) ≅ H̃_{k-1}(Sⁿ⁻¹)` and the final `H_k(Sⁿ)`
computation. The root `main : True` is **vestigial scaffolding** — prove it
trivially; the real product is the Forward-built pieces harvested to the Library.

This is a **research-level formalization** (a genuine mathlib gap). Decompose
aggressively via Backward; ALWAYS search mathlib first (grep + loogle) before
building anything — cite what exists, only Forward-build the genuinely missing.

### The base (confirmed FQNs — use these, do not reinvent)

mathlib's singular homology is **categorical** (via simplicial sets + Dold–Kan),
NOT the naive free ℤ-module on singular simplices:
- `AlgebraicTopology.singularChainComplexFunctor : C ⥤ TopCat ⥤ ChainComplex C ℕ`
  (take `C := ModuleCat ℤ`). Pipeline `TopCat → SSet → ChainComplex`.
- `AlgebraicTopology.singularHomologyFunctor (n) : C ⥤ TopCat ⥤ C`.
- `TopCat.singularHomology₀Iso` (H₀), `TopCat.Homotopy.congr_homologyMap_singularChainComplexFunctor` (homotopy invariance).

The **homological-algebra LES machinery is COMPLETE — use it, do NOT rebuild**:
- `CategoryTheory.ShortComplex.ShortExact` (short exact sequence of chain complexes).
- `ShortComplex.ShortExact.δ` (the snake-lemma connecting map `H_i(X₃) ⟶ H_j(X₁)`).
- `ShortComplex.ShortExact.homology_exact₁ / homology_exact₂ / homology_exact₃`
  (three-term exactness at each spot). **From a `ShortExact` of chain complexes,
  the long exact sequence in homology is FREE via these.**
- `SSet.sd` (simplicial-set barycentric subdivision) exists — but the subdivision
  quasi-iso ON SINGULAR CHAINS is NOT assembled; that is the crux to build.

### What to build (the topological input to MV)

Standard structure (Hatcher §2.1), adapted to the categorical framework:
1. For an open cover `{A, B}` of a space `X` (`A ∪ B = univ`, `A B` open): the
   sub-chain-complexes `C(A), C(B) ⊆ C(X)` (chains supported in A / B) and their
   sum `C(A)+C(B)`.
2. The short exact sequence `0 → C(A∩B) → C(A)⊕C(B) → C(A)+C(B) → 0` — short-exact
   by construction (the EASY part; package as a `ShortComplex.ShortExact`).
3. **THE CRUX** — the small-simplices theorem: the inclusion `C(A)+C(B) ↪ C(X)` is
   a **quasi-isomorphism** (iso on homology). Via the barycentric subdivision
   operator `S` on singular chains + a chain homotopy `T` with `∂T + T∂ = S − id`,
   iterated (Lebesgue number of the cover) until every simplex is subordinate to
   `{A,B}`. Build `S`, prove it is a chain map, build `T`, then the quasi-iso.
4. Assemble: combine (2) + (3) → the MV long exact sequence
   `⋯ → H_n(A∩B) → H_n(A)⊕H_n(B) → H_n(X) → H_{n-1}(A∩B) → ⋯`
   using the `ShortExact` machinery above.

### Deliverables

Forward-build these; Backward-decompose the hard ones; `MarkDeliverable` the
reusable results; then `Ingest`:
- the subdivision operator `S` + its chain homotopy `T` (`∂T + T∂ = S − id`),
- the small-simplices quasi-isomorphism `C(A)+C(B) ↪ C(X)` (the crux),
- the MV short exact sequence,
- **the MV long exact sequence** (the top claim).

If a genuine wall is hit (e.g. the categorical framework blocks the subdivision
descent with no tractable route), it is fine to stall — that is diagnostic data,
not a failure to paper over. Do NOT introduce axioms or `sorry`-bearing shortcuts.
