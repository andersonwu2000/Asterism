import Library.LinearAlgebra.InvariantFactor.GridReindex
import Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition
import Mathlib

open Library.LinearAlgebra.InvariantFactor.GridReindex
open Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition

namespace Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition

-- Recombine prime-power cyclic summands into an invariant-factor (divisibility) chain.
-- `recombine_unified` (Backward, the crux): produces the column grid — distinct monic
--   primes `q`, an exponent grid `c` non-decreasing along columns — and the K[X]-linear
--   iso onto `⨁ K[X]/(∏ₜ q t ^ c k t)`; this is the witness-bearing existence kept unified.
-- `divchain_column_products` (Builder, witness-independent): column products with
--   per-prime non-decreasing exponents form a divisibility chain.
-- Closer: take f k := ∏ₜ q t ^ c k t; monic from `monic_prod_of_monic`/`Monic.pow`,
--   non-unit from the grid, divisibility from `divchain_column_products`, iso direct.
theorem recombine_invariant_factors {K : Type*} [Field K] {ι : Type*} [Fintype ι]
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

-- Invariant factor decomposition = primary (prime-power) decomposition, then
-- recombination of the prime-power cyclic summands into a divisibility chain.
-- `primary_form` (SG1): the K[X]-module `AEval' T` splits as `⨁ K[X]/(p i ^ e i)`
--   with `p i` monic irreducible (mathlib structure theorem for f.g. torsion PID modules).
-- `recombine_invariant_factors` (SG2, abstract over T): regroup any such prime-power
--   direct sum into invariant factors `f 0 ∣ f 1 ∣ ... ` (monic, non-unit) via CRT.
-- Combinator: transport `AEval' T` across `equiv1.trans equiv2`; side conditions from SG2.
theorem main : ∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (r : ℕ) (f : Fin r → Polynomial K),
    (∀ i, (f i).Monic) ∧
    (∀ i, ¬ IsUnit (f i)) ∧
    (∀ i j, i ≤ j → f i ∣ f j) ∧
    Nonempty (Module.AEval' T ≃ₗ[Polynomial K]
      DirectSum (Fin r)
        (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))  := by
  intro K _ V _ _ _ T
  obtain ⟨ι, _, p, hirr, hmon, e, ⟨equiv1⟩⟩ := primary_form T
  obtain ⟨r, f, hfmon, hfunit, hfdvd, ⟨equiv2⟩⟩ := recombine_invariant_factors p e hirr hmon
  exact ⟨r, f, hfmon, hfunit, hfdvd, ⟨equiv1.trans equiv2⟩⟩

end Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition
