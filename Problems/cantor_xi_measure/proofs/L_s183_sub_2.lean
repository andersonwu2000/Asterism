import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set

/-- The right affine image of each Cantor iterate lies in [(1+ξ)/2, 1]. -/
theorem s183_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ∀ n : ℕ,
    (fun x => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n ⊆ Set.Icc ((1 + ξ) / 2) 1 := by
  intro ξ hξ₁ hξ₂ n
  have hbound : ∀ m, cantorXi ξ m ⊆ Set.Icc 0 1 := by
    intro m
    induction m with
    | zero => exact Set.Subset.refl _
    | succ k ih =>
      show ((fun x => (1 - ξ) / 2 * x) '' cantorXi ξ k) ∪
           ((fun x => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ k) ⊆ Set.Icc 0 1
      rintro x (⟨y, hy, rfl⟩ | ⟨y, hy, rfl⟩)
      · have hy01 := ih hy
        refine Set.mem_Icc.mpr ⟨mul_nonneg (by linarith) hy01.1, ?_⟩
        have h := mul_le_mul_of_nonneg_left hy01.2 (show (0 : ℝ) ≤ (1 - ξ) / 2 by linarith)
        simp only [mul_one] at h
        linarith
      · have hy01 := ih hy
        refine Set.mem_Icc.mpr
          ⟨by linarith [mul_nonneg (show (0 : ℝ) ≤ (1 - ξ) / 2 by linarith) hy01.1], ?_⟩
        have h := mul_le_mul_of_nonneg_left hy01.2 (show (0 : ℝ) ≤ (1 - ξ) / 2 by linarith)
        simp only [mul_one] at h
        linarith
  rintro z ⟨x, hx, rfl⟩
  have hx01 := hbound n hx
  refine Set.mem_Icc.mpr
    ⟨by linarith [mul_nonneg (show (0 : ℝ) ≤ (1 - ξ) / 2 by linarith) hx01.1], ?_⟩
  have h := mul_le_mul_of_nonneg_left hx01.2 (show (0 : ℝ) ≤ (1 - ξ) / 2 by linarith)
  simp only [mul_one] at h
  linarith

end Problems.cantor_xi_measure
