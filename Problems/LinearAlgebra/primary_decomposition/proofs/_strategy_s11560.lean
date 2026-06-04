import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- Direct induction on n (no sub-goals; leaf-bypass).
-- Peel q 0 off the product via `Fin.prod_univ_succ`; q 0 is coprime to the tail
-- ∏ q i.succ (pairwise coprimality + `IsCoprime.prod_right`), so the 2-factor
-- `Polynomial.sup_ker_aeval_eq_ker_aeval_mul_of_coprime` splits the kernel into
-- ker(aeval T (q 0)) ⊔ ker(aeval T (tail)); the IH bounds the tail kernel.
theorem s11560
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    LinearMap.ker (Polynomial.aeval T (∏ i, q i)) ≤
      ⨆ i, LinearMap.ker (Polynomial.aeval T (q i))  := by
  induction n with
  | zero => simp [Module.End.one_eq_id, LinearMap.ker_id]
  | succ n ih =>
    rw [Fin.prod_univ_succ]
    have hco : IsCoprime (q 0) (∏ i : Fin n, q i.succ) := by
      apply IsCoprime.prod_right
      intro i _
      exact hcop (Fin.succ_ne_zero i).symm
    rw [← Polynomial.sup_ker_aeval_eq_ker_aeval_mul_of_coprime T hco]
    apply sup_le
    · exact le_iSup (fun i => LinearMap.ker (Polynomial.aeval T (q i))) 0
    · refine le_trans (ih (fun i => q i.succ) ?_) ?_
      · intro i j hij
        exact hcop (fun h => hij (Fin.succ_injective n h))
      · apply iSup_le
        intro i
        exact le_iSup (fun i => LinearMap.ker (Polynomial.aeval T (q i))) i.succ

end Problems.LinearAlgebra.primary_decomposition
