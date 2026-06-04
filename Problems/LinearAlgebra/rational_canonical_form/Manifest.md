---
problem: LinearAlgebra.rational_canonical_form
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.rational_canonical_form — Rational (Frobenius) canonical form

## Statement
∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (r : ℕ) (f : Fin r → Polynomial K),
    (∀ i, (f i).Monic) ∧
    (∀ i, ¬ IsUnit (f i)) ∧
    (∀ i j, i ≤ j → f i ∣ f j) ∧
    ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
      LinearMap.toMatrix b b T
        = Matrix.blockDiagonal' (fun i => companionMatrix (f i))

## Setting
- `K` arbitrary field; `V` finite-dim; `T : V →ₗ[K] V`.
- `companionMatrix f` (in `Defs.lean`): the `natDegree × natDegree` matrix of
  "multiply by `x`" on `K[X]/(f)` in the basis `1, x, …, x^{n-1}` (subdiagonal 1's,
  negated coefficients of `f` in the last column).
- Conclusion (the **rational / Frobenius canonical form**): there are invariant factors
  `f₁ ∣ f₂ ∣ … ∣ f_r` (monic, non-unit) and a basis of `V` — indexed by
  `Σ i, Fin (f i).natDegree` (the per-block cyclic bases concatenated) — in which `T`'s
  matrix is the block-diagonal matrix of the companion matrices of the invariant factors.

## Route

This is the **matrix form** of the invariant-factor (cyclic) decomposition, which is
already in the Library (#95). The new work is turning each abstract cyclic summand
`K[X]/(f_i)` into its concrete companion-matrix block and assembling the block diagonal.
Mathlib has NO companion matrix or RCF — `companionMatrix` is defined locally in `Defs.lean`;
do not search mathlib for it.

1. **Get the cyclic decomposition (cite Library #95).** From
   `Library.LinearAlgebra.InvariantFactor.*` obtain the invariant factors
   `f₁ ∣ … ∣ f_r` (monic, non-unit) and the `K[X]`-linear iso
   `Module.AEval' T ≃ₗ[K[X]] ⨁ᵢ K[X]/(f_i)` (read `Library/INDEX.md` for the exact decl
   names — the keystone is the `InvariantFactorDecomposition` root plus
   `recombine_invariant_factors`). Do NOT re-derive the PID structure theorem or the
   primary→invariant-factor recombination — those are #95 / mathlib.
2. **Per-block companion form.** For each `i`, the cyclic `K[X]`-module `K[X]/(f_i)` has the
   `K`-basis `1, x, …, x^{deg f_i - 1}`; in that basis the `x`-action (= `T` transported)
   is exactly `companionMatrix (f i)`. Prove `toMatrix (block basis) (block basis) (x•·)
   = companionMatrix (f i)` by computing each column (`Defs` companion def + `Polynomial`
   `modByMonic` / `coeff` of `x * x^j`).
3. **Assemble.** Concatenate the per-block bases into `b : Basis (Σ i, Fin (f i).natDegree)`
   (transport the `⨁` iso to a `Basis` via `Basis.ofEquivFun` / `DirectSum` basis helpers),
   and show `toMatrix b b T = blockDiagonal'` of the blocks — off-diagonal blocks vanish
   because each cyclic summand is `T`-invariant. Tools: `Matrix.blockDiagonal'`,
   `LinearMap.toMatrix`, `Basis.reindex`, `DirectSum` / `Submodule.IsInternal` basis APIs.

## Lemma hints

Library (cite, do not reconstruct):
- `Library.LinearAlgebra.InvariantFactor.*` — invariant-factor / cyclic decomposition
  (#95): the `f₁ ∣ … ∣ f_r` and `AEval' T ≃ₗ[K[X]] ⨁ K[X]/(f_i)`. Read `Library/INDEX.md`
  for exact decl names (`InvariantFactorDecomposition` root, `recombine_invariant_factors`,
  `PolynomialCRT.*`, `PrimaryDecomposition.exists_monic_quot_equiv`).
- `Library.LinearAlgebra.PrimaryDecomposition.*` (#41) — if a primary-level step is needed.

Mathlib (foundational):
- `Module.AEval'`, `Module.AEval'.of` (the `K[X]`-module of `T`).
- `Matrix.blockDiagonal'`, `LinearMap.toMatrix`, `Basis`, `Basis.reindex`,
  `Basis.ofEquivFun`, `DirectSum.IsInternal` / `Submodule` basis constructions.
- `Polynomial.modByMonic`, `Polynomial.coeff`, `Polynomial.Monic`, `AdjoinRoot` (the
  `K[X]/(f)` cyclic module + its power basis, if convenient: `AdjoinRoot.powerBasis`).

## R1 — search before reconstructing (hard rule)

Before introducing any new `lemma`/`def`/`structure`/`class`: `Grep` mathlib + `loogle`;
reuse + thin bridge if a match exists. Do NOT rebuild the PID structure theorem, the
invariant-factor decomposition (#95 Library), or the `K[X]`-module machinery. `companionMatrix`
is the ONE intended local definition (already in `Defs.lean`); everything else is cite-or-bridge.
New Forwards must open with `## Forward rationale — Grep + Loogle confirmed missing: <keywords>`.

## Forbidden angles
- Searching mathlib for a ready-made companion matrix / rational canonical form — there is
  none; `companionMatrix` is local. (If you DO find one, surface via `RequestUserAmend`.)
- Re-deriving the cyclic/invariant-factor decomposition instead of citing Library #95.
