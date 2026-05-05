import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set

/-- The left affine image of each Cantor iterate lies in [0, (1-ξ)/2]. -/
theorem s183_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ∀ n : ℕ,
    (fun x => (1 - ξ) / 2 * x) '' cantorXi ξ n ⊆ Set.Icc 0 ((1 - ξ) / 2) := by
  intro ξ hξ₁ hξ₂ n
  have hcoeff : 0 ≤ (1 - ξ) / 2 := by linarith
  have hbound : ∀ m : ℕ, cantorXi ξ m ⊆ Set.Icc 0 1 := by
    intro m
    induction m with
    | zero => simp [cantorXi]
    | succ m ih =>
      intro x hx
      simp only [cantorXi, Set.mem_union, Set.mem_image] at hx
      rcases hx with ⟨y, hy, rfl⟩ | ⟨y, hy, rfl⟩
      · have hy' := ih hy
        simp only [Set.mem_Icc] at hy' ⊢
        exact ⟨mul_nonneg hcoeff hy'.1,
               by nlinarith [mul_le_mul_of_nonneg_left hy'.2 hcoeff]⟩
      · have hy' := ih hy
        simp only [Set.mem_Icc] at hy' ⊢
        exact ⟨by nlinarith [mul_nonneg hcoeff hy'.1],
               by nlinarith [mul_le_mul_of_nonneg_left hy'.2 hcoeff]⟩
  intro y hy
  obtain ⟨x, hx, rfl⟩ := hy
  have hx' := hbound n hx
  simp only [Set.mem_Icc] at hx' ⊢
  exact ⟨mul_nonneg hcoeff hx'.1,
         by nlinarith [mul_le_mul_of_nonneg_left hx'.2 hcoeff]⟩

end Problems.cantor_xi_measure
