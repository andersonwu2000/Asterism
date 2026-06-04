---
problem: LinearAlgebra.primary_decomposition
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.primary_decomposition — Primary decomposition of an endomorphism

## Statement
∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (n : ℕ) (p : Fin n → Polynomial K) (e : Fin n → ℕ),
    (∀ i, Irreducible (p i)) ∧
    (∀ i, (p i).Monic) ∧
    (∀ i, 0 < e i) ∧
    Function.Injective p ∧
    minpoly K T = ∏ i, p i ^ e i ∧
    DirectSum.IsInternal
      (fun i : Fin n => LinearMap.ker ((Polynomial.aeval T) (p i ^ e i)))

## Setting
- `K` an arbitrary field (NOT assumed algebraically closed — this is the general-field
  primary decomposition, indexed by the monic irreducible factors of the minimal
  polynomial, not by eigenvalues).
- `V` finite-dim `K`-vector space, `T : V →ₗ[K] V` an endomorphism.
- Conclusion: writing `minpoly K T = ∏ pᵢ^{eᵢ}` (distinct monic irreducibles `pᵢ`,
  multiplicities `eᵢ ≥ 1`), the primary components `Vᵢ := ker (pᵢ(T)^{eᵢ})` form an internal
  direct sum `V = ⨁ Vᵢ`. This is the standard textbook **primary decomposition theorem**
  (the foundation under Jordan / rational canonical form).

## Route (recommended)

This is a genuine Mathlib gap (mathlib only has the *eigenvalue* decomposition for
algebraically-closed fields via generalized eigenspaces). Build the general-field version:

1. `minpoly K T` is monic (`minpoly.monic`, T is integral as `V` is finite-dim) and splits
   into monic irreducibles in the UFD `K[X]`: `minpoly K T = ∏ pᵢ^{eᵢ}`. Extract the
   factorization (`UniqueFactorizationMonoid` / `Polynomial.Monic` factorization,
   `Polynomial.factors`, or `Multiset`-based `normalizedFactors`); package as `p : Fin n → K[X]`,
   `e : Fin n → ℕ` with distinct monic irreducible `pᵢ` and `eᵢ ≥ 1`.
2. The factors `pᵢ^{eᵢ}` are **pairwise coprime** (`IsCoprime`) in `K[X]` (distinct
   irreducibles). Coprimality is the engine of the whole decomposition.
3. **Spanning** `⨆ ker(pᵢ(T)^{eᵢ}) = ⊤`: since `∏ pᵢ^{eᵢ} = minpoly K T` annihilates `T`
   (`aeval T (minpoly K T) = 0` via `minpoly.aeval`), a Bézout/partition-of-unity argument
   from pairwise coprimality (`IsCoprime` ⇒ `∃ a b, a*f + b*g = 1`) writes `id = Σ` of
   projections onto the kernels.
4. **Independence** `iSupIndep (fun i => ker(pᵢ(T)^{eᵢ}))`: again from coprimality —
   `ker(pᵢ(T)^{eᵢ}) ∩ Σ_{j≠i} ker(pⱼ(T)^{eⱼ}) = ⊥`.
5. Assemble (3)+(4) into `DirectSum.IsInternal` (`DirectSum.isInternal_submodule_iff_iSupIndep_and_iSup_eq_top`
   or `DirectSum.IsInternal` constructor).

Heavier alternative (if the Bézout route stalls): view `V` as a `K[X]`-module via
`Module.AEval' T` (`X • v = T v`), which is torsion in finite dim
(`Module.AEval.isTorsion_of_finiteDimensional`), then apply the PID prime-power torsion
decomposition `Submodule.isInternal_prime_power_torsion_of_pid` and transport the
`K[X]`-submodules back to `ker (pᵢ(T)^{eᵢ})` in `V`. This reuses mathlib's PID structure
theorem but pays a translation cost (AEval' submodule ↔ `LinearMap.ker` in `V`).

## Lemma hints (Mathlib — this problem is the base of the stage-3 chain, cites no Library)

- `minpoly.monic`, `minpoly.aeval`, `minpoly.ne_zero` — the minimal polynomial of `T`.
- `Polynomial.aeval`, `Polynomial.aeval_endomorphism` / `Module.End` algebra structure.
- `IsCoprime`, `IsCoprime.pow`, `Polynomial.isCoprime_of_isUnit_of_...` / coprimality of
  distinct monic irreducibles; `UniqueFactorizationMonoid.normalizedFactors`,
  `Polynomial.Monic` factorization, `Associated`.
- `Module.End.genEigenspace`, `Module.End.iSupIndep_genEigenspace` /
  `independent_maxGenEigenspace` (for the independence pattern; note these are eigenvalue
  versions — the irreducible-factor version is the gap to build).
- `DirectSum.IsInternal`,
  `DirectSum.isInternal_submodule_iff_iSupIndep_and_iSup_eq_top`, `Submodule.iSupIndep`.
- `Module.AEval'`, `Module.AEval.isTorsion_of_finiteDimensional`,
  `Submodule.isInternal_prime_power_torsion_of_pid` (heavy alternative route).

## R1 — search before reconstructing (hard rule)

Before introducing any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the name/shape you intend to
   build. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: reuse it; write a thin bridge lemma. Do not rebuild the
   minimal polynomial, UFD factorization, coprimality, generalized-eigenspace, or
   PID-structure machinery — mathlib has them.
4. Only after confirmed missing, inject a new Forward whose `## Forward rationale` first line
   states `Grep + Loogle confirmed missing` with the searched keywords.

## Forbidden angles

- Restricting `K` to algebraically closed / `ℂ` and citing `iSup_maxGenEigenspace_eq_top` —
  that is the *eigenvalue* decomposition already in mathlib, not the general-field primary
  decomposition this problem asks for.
- Citing the entire result as a single mathlib theorem if you find one — surface via
  `RequestUserAmend` (the problem is then done).
