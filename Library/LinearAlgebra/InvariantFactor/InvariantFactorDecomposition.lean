import Library.LinearAlgebra.InvariantFactor.GridReindex
import Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition
import Mathlib

open Library.LinearAlgebra.InvariantFactor.GridReindex
open Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition

/-!
# Invariant factor decomposition

This file assembles the invariant factor decomposition for finitely generated torsion
`K[X]`-modules. Starting from a primary (prime-power cyclic) decomposition, it applies
the Chinese Remainder Theorem column-wise to merge the prime-power summands into a
divisibility chain `f 0 ∣ f 1 ∣ ⋯`, yielding the classical invariant factor form.
The main result (`main`) specialises this to the `K[X]`-module `AEval' T` associated
with a finite-dimensional linear operator `T`.
-/

namespace Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition

variable {K : Type*} [Field K]

/-- Given a family of monic irreducible polynomials `p i` with exponents `e i`,
any direct sum `⨁ K[X]/(p i ^ e i)` is linearly isomorphic over `K[X]` to a direct
sum `⨁ K[X]/(f k)` whose generators are monic, non-unit, and satisfy `f i ∣ f j` for
`i ≤ j` — i.e., they are invariant factors. -/
theorem recombine_invariant_factors {ι : Type*} [Fintype ι]
    (p : ι → Polynomial K) (e : ι → ℕ) (hirr : ∀ i, Irreducible (p i))
    (hmon : ∀ i, (p i).Monic) :
    ∃ (r : ℕ) (f : Fin r → Polynomial K),
      (∀ i, (f i).Monic) ∧ (∀ i, ¬ IsUnit (f i)) ∧ (∀ i j, i ≤ j → f i ∣ f j) ∧
      Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
        ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun k => Polynomial K ⧸ Submodule.span (Polynomial K) {f k}))  := by
  obtain ⟨r, s, q, c, hqmon, hcmono, hnu, hequiv⟩ :
      ∃ (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ),
        (∀ t, (q t).Monic) ∧
        (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
        (∀ k, ¬ IsUnit (∏ t, q t ^ c k t)) ∧
        Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
          ≃ₗ[Polynomial K]
          DirectSum (Fin r) (fun k => Polynomial K ⧸ Submodule.span (Polynomial K) {∏ t, q t ^ c k t})) :=
    recombine_unified p e hirr hmon
  refine ⟨r, fun k => ∏ t, q t ^ c k t, ?_, hnu, ?_, hequiv⟩
  · intro k
    exact Polynomial.monic_prod_of_monic _ _ (fun t _ => (hqmon t).pow _)
  · exact divchain_column_products q c hcmono

/-- Invariant factor decomposition of a finite-dimensional linear operator.
For any linear endomorphism `T` of a finite-dimensional `K`-vector space `V`, the
`K[X]`-module `AEval' T` is isomorphic to a direct sum `⨁ K[X]/(f i)` where each
`f i` is monic and non-unit and the generators satisfy the divisibility chain
`f 0 ∣ f 1 ∣ ⋯`. -/
theorem main {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) :
    ∃ (r : ℕ) (f : Fin r → Polynomial K),
      (∀ i, (f i).Monic) ∧
      (∀ i, ¬ IsUnit (f i)) ∧
      (∀ i j, i ≤ j → f i ∣ f j) ∧
      Nonempty (Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r)
          (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))  := by
  obtain ⟨ι, _, p, hirr, hmon, e, ⟨equiv1⟩⟩ := primary_form T
  obtain ⟨r, f, hfmon, hfunit, hfdvd, ⟨equiv2⟩⟩ := recombine_invariant_factors p e hirr hmon
  exact ⟨r, f, hfmon, hfunit, hfdvd, ⟨equiv1.trans equiv2⟩⟩

end Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition
