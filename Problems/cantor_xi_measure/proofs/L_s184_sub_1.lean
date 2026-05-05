import Mathlib

namespace Problems.cantor_xi_measure

theorem s184_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ (S : Set ℝ), S ⊆ Set.Icc 0 1 →
    (fun x => (1 - ξ) / 2 * x) '' S ⊆ Set.Icc 0 1 := by
  intro ξ hξ₁ hξ₂ S hS y hy
  obtain ⟨x, hxS, rfl⟩ := hy
  have hx := hS hxS
  simp only [Set.mem_Icc] at hx ⊢
  have hfac : 0 ≤ (1 - ξ) / 2 := by linarith
  refine ⟨mul_nonneg hfac hx.1, ?_⟩
  calc (1 - ξ) / 2 * x
      ≤ (1 - ξ) / 2 * 1 := mul_le_mul_of_nonneg_left hx.2 hfac
    _ = (1 - ξ) / 2 := mul_one _
    _ ≤ 1 := by linarith

end Problems.cantor_xi_measure
