import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set MeasureTheory

/-- The two affine pieces at each step are disjoint: left image ⊆ [0,(1-ξ)/2], right ⊆ [(1+ξ)/2,1]. -/
theorem s185_sub_4 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ,
    Disjoint ((fun x : ℝ => (1 - ξ) / 2 * x) '' cantorXi ξ n)
             ((fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n) := by
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
  have hleft : (fun x : ℝ => (1 - ξ) / 2 * x) '' cantorXi ξ n ⊆ Set.Icc 0 ((1 - ξ) / 2) := by
    intro z hz
    obtain ⟨x, hx, rfl⟩ := hz
    have hx' := hbound n hx
    simp only [Set.mem_Icc] at hx' ⊢
    exact ⟨mul_nonneg hcoeff hx'.1,
           by nlinarith [mul_le_mul_of_nonneg_left hx'.2 hcoeff]⟩
  have hright : (fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n ⊆
      Set.Icc ((1 + ξ) / 2) 1 := by
    intro z hz
    obtain ⟨x, hx, rfl⟩ := hz
    have hx' := hbound n hx
    simp only [Set.mem_Icc] at hx' ⊢
    exact ⟨by linarith [mul_nonneg hcoeff hx'.1],
           by nlinarith [mul_le_mul_of_nonneg_left hx'.2 hcoeff]⟩
  apply Disjoint.mono hleft hright
  rw [Set.disjoint_left]
  intro z hz1 hz2
  simp only [Set.mem_Icc] at hz1 hz2
  linarith

end Problems.cantor_xi_measure
