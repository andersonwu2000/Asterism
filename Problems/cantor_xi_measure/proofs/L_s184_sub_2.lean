import Mathlib

namespace Problems.cantor_xi_measure

theorem s184_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ (S : Set ℝ), S ⊆ Set.Icc 0 1 →
    (fun x => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' S ⊆ Set.Icc 0 1 := by
  intro ξ hξ₁ hξ₂ S hS
  rintro y ⟨x, hxS, rfl⟩
  have hx := hS hxS
  rw [Set.mem_Icc] at hx ⊢
  obtain ⟨hx0, hx1⟩ := hx
  constructor <;> nlinarith

end Problems.cantor_xi_measure
