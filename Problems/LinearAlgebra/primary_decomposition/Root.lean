import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs.L_exists_finpow_factorization
import Problems.LinearAlgebra.primary_decomposition.proofs.L_is_internal_ker_aeval_of_pairwise_coprime

namespace Problems.LinearAlgebra.primary_decomposition

-- main: assemble primary decomposition from exists_finpow_factorization
-- (unique factorization of minpoly into distinct monic irreducibles)
-- and is_internal_ker_aeval_of_pairwise_coprime (CRT kernel-decomposition engine).
theorem main : ∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (n : ℕ) (p : Fin n → Polynomial K) (e : Fin n → ℕ),
    (∀ i, Irreducible (p i)) ∧
    (∀ i, (p i).Monic) ∧
    (∀ i, 0 < e i) ∧
    Function.Injective p ∧
    minpoly K T = ∏ i, p i ^ e i ∧
    DirectSum.IsInternal
      (fun i : Fin n => LinearMap.ker ((Polynomial.aeval T) (p i ^ e i))) := by
  intro K _ V _ _ _ T
  have hT_int : IsIntegral K T := Algebra.IsIntegral.isIntegral T
  have hmonic : (minpoly K T).Monic := minpoly.monic hT_int
  have hne : minpoly K T ≠ 0 := minpoly.ne_zero hT_int
  obtain ⟨n, p, e, hirr, hmono, hpos, hinj, hcop_p, hfact⟩ :=
    exists_finpow_factorization (minpoly K T) hmonic hne
  exact ⟨n, p, e, hirr, hmono, hpos, hinj, hfact,
    is_internal_ker_aeval_of_pairwise_coprime T (fun i => p i ^ e i)
      (fun _ _ hij => (hcop_p _ _ hij).pow)
      (by rw [← hfact, minpoly.aeval K T]; exact LinearMap.ker_zero)⟩

end Problems.LinearAlgebra.primary_decomposition
