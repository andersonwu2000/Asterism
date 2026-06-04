import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs

namespace Problems.LinearAlgebra.normal_diagonalization

-- entry_kind: Builder
-- sum_norm_sq_eq_single_imp_zero: if a sum of squared norms equals its i-th term,
-- all other terms vanish (nonneg sum collapsed to one summand via erase decomposition)
theorem sum_norm_sq_eq_single_imp_zero {n : ℕ} (f : Fin n → ℂ) (i : Fin n)
    (h : ∑ k, ‖f k‖ ^ 2 = ‖f i‖ ^ 2) :
    ∀ k, k ≠ i → f k = 0 := by
  intro k hk
  have hnn : ∀ j : Fin n, 0 ≤ ‖f j‖ ^ 2 := fun j => sq_nonneg _
  have hge : 0 ≤ ∑ j ∈ Finset.univ.erase i, ‖f j‖ ^ 2 :=
    Finset.sum_nonneg (fun j _ => hnn j)
  have hsplit : (∑ j ∈ Finset.univ.erase i, ‖f j‖ ^ 2) + ‖f i‖ ^ 2 =
      ∑ j : Fin n, ‖f j‖ ^ 2 :=
    Finset.sum_erase_add Finset.univ (fun j => ‖f j‖ ^ 2) (Finset.mem_univ i)
  have key : ∑ j ∈ Finset.univ.erase i, ‖f j‖ ^ 2 = 0 := by
    linarith [hsplit.trans h]
  have hk2 : ‖f k‖ ^ 2 = 0 :=
    le_antisymm
      (key ▸ Finset.single_le_sum (fun j _ => hnn j)
        (Finset.mem_erase.mpr ⟨hk, Finset.mem_univ k⟩))
      (hnn k)
  exact norm_eq_zero.mp (by nlinarith [norm_nonneg (f k)])

end Problems.LinearAlgebra.normal_diagonalization

