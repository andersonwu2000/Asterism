import Mathlib
namespace Problems.Minif2f.aime_1996_p5

-- vieta_sum: a+b+c = -3 via Vieta for the monic cubic f(x) = x^3 + 3x^2 + 4x - 11.
-- Subtracting root equations pairwise and dividing by (a-b) and (b-c) yields the sum.
theorem vieta_sum : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11)
    (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t)
    (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0)
    (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0)
    (h₈ : List.Pairwise (· ≠ ·) [a, b, c]),
    a + b + c = -3 := by
  intro a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  simp [h₀] at h₂ h₃ h₄
  simp [List.pairwise_cons] at h₈
  obtain ⟨⟨hab, hac⟩, hbc⟩ := h₈
  have hab' : a - b ≠ 0 := sub_ne_zero.mpr hab
  have hbc' : b - c ≠ 0 := sub_ne_zero.mpr hbc
  have hac' : a - c ≠ 0 := sub_ne_zero.mpr hac
  have eq_ab : (a - b) * (a ^ 2 + a * b + b ^ 2 + 3 * (a + b) + 4) = 0 := by ring_nf; linarith
  have key_ab : a ^ 2 + a * b + b ^ 2 + 3 * (a + b) + 4 = 0 :=
    (mul_eq_zero.mp eq_ab).resolve_left hab'
  have eq_ac : (a - c) * (a ^ 2 + a * c + c ^ 2 + 3 * (a + c) + 4) = 0 := by ring_nf; linarith
  have key_ac : a ^ 2 + a * c + c ^ 2 + 3 * (a + c) + 4 = 0 :=
    (mul_eq_zero.mp eq_ac).resolve_left hac'
  have eq_bc : (b - c) * (a + b + c + 3) = 0 := by nlinarith [key_ab, key_ac]
  linarith [(mul_eq_zero.mp eq_bc).resolve_left hbc']

end Problems.Minif2f.aime_1996_p5
