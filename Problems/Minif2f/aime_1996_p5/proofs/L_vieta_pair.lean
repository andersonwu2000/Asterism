import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs

namespace Problems.Minif2f.aime_1996_p5

-- vieta_pair: ab+bc+ca=4 via polynomial-difference factoring on distinct cubic roots
-- Subtracts pairs of root equations to get quotient polys, uses a≠c to pin a+b+c=-3,
-- then reads off ab+bc+ca=4 by substituting c=-3-a-b and applying the quotient.
theorem vieta_pair : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11)
    (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t)
    (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0)
    (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0)
    (h₈ : List.Pairwise (· ≠ ·) [a, b, c]),
    a*b + b*c + c*a = 4 := by
  intro a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  have h₂' : a ^ 3 + 3 * a ^ 2 + 4 * a - 11 = 0 := by linarith [h₀ a, h₂]
  have h₃' : b ^ 3 + 3 * b ^ 2 + 4 * b - 11 = 0 := by linarith [h₀ b, h₃]
  have h₄' : c ^ 3 + 3 * c ^ 2 + 4 * c - 11 = 0 := by linarith [h₀ c, h₄]
  simp only [List.pairwise_cons, List.mem_cons, List.mem_nil_iff, or_false] at h₈
  obtain ⟨h_a_ne, hbc_forall, -⟩ := h₈
  have hab : a ≠ b := h_a_ne b (Or.inl rfl)
  have hac : a ≠ c := h_a_ne c (Or.inr rfl)
  have hbc : b ≠ c := hbc_forall c rfl
  have hne_ab : b - a ≠ 0 := sub_ne_zero.mpr (Ne.symm hab)
  have hne_cb : c - b ≠ 0 := sub_ne_zero.mpr (Ne.symm hbc)
  have hne_ca : a - c ≠ 0 := sub_ne_zero.mpr hac
  have h_ab_quot : a ^ 2 + a * b + b ^ 2 + 3 * a + 3 * b + 4 = 0 := by
    have key : (b - a) * (a ^ 2 + a * b + b ^ 2 + 3 * a + 3 * b + 4) = 0 := by
      linear_combination h₃' - h₂'
    exact (mul_eq_zero.mp key).resolve_left hne_ab
  have h_bc_quot : b ^ 2 + b * c + c ^ 2 + 3 * b + 3 * c + 4 = 0 := by
    have key : (c - b) * (b ^ 2 + b * c + c ^ 2 + 3 * b + 3 * c + 4) = 0 := by
      linear_combination h₄' - h₃'
    exact (mul_eq_zero.mp key).resolve_left hne_cb
  have hsum : a + b + c = -3 := by
    have key : (a - c) * (a + b + c + 3) = 0 := by linear_combination h_ab_quot - h_bc_quot
    have hzero : a + b + c + 3 = 0 := (mul_eq_zero.mp key).resolve_left hne_ca
    linarith
  have hc : c = -3 - a - b := by linarith
  have heq : a * b + b * c + c * a = -(a ^ 2 + a * b + b ^ 2 + 3 * a + 3 * b) := by
    rw [hc]; ring
  linarith [h_ab_quot]

end Problems.Minif2f.aime_1996_p5
