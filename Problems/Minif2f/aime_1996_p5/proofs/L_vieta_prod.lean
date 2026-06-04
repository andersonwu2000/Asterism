import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs

namespace Problems.Minif2f.aime_1996_p5

-- vieta_prod: abc = 11 from three distinct roots of x^3+3x^2+4x-11=0 via Vieta.
-- Key steps: subtract root equations pairwise to get a²+ab+b²+3(a+b)+4=0,
-- then subtract those to get a+b+c=-3, hence ab=4+3c+c², so abc=c(4+3c+c²)=11.
theorem vieta_prod : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11)
    (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t)
    (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0)
    (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0)
    (h₈ : List.Pairwise (· ≠ ·) [a, b, c]),
    a*b*c = 11 := by
  intro a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  simp [h₀] at h₂ h₃ h₄
  rw [List.pairwise_cons] at h₈
  obtain ⟨hmem1, h₈'⟩ := h₈
  have hab : a ≠ b := hmem1 b (by simp)
  have hac : a ≠ c := hmem1 c (by simp)
  rw [List.pairwise_cons] at h₈'
  obtain ⟨hmem2, _⟩ := h₈'
  have hbc : b ≠ c := hmem2 c (by simp)
  have hD : a ^ 2 + a * b + b ^ 2 + 3 * a + 3 * b + 4 = 0 := by
    have : (a - b) * (a ^ 2 + a * b + b ^ 2 + 3 * a + 3 * b + 4) = 0 := by nlinarith
    rcases mul_eq_zero.mp this with h | h
    · exact absurd (sub_eq_zero.mp h) hab
    · linarith
  have hE : b ^ 2 + b * c + c ^ 2 + 3 * b + 3 * c + 4 = 0 := by
    have : (b - c) * (b ^ 2 + b * c + c ^ 2 + 3 * b + 3 * c + 4) = 0 := by nlinarith
    rcases mul_eq_zero.mp this with h | h
    · exact absurd (sub_eq_zero.mp h) hbc
    · linarith
  have hsum : a + b + c = -3 := by
    have : (a - c) * (a + b + c + 3) = 0 := by nlinarith
    rcases mul_eq_zero.mp this with h | h
    · exact absurd (sub_eq_zero.mp h) hac
    · linarith
  have hab_eq : a * b = 4 + 3 * c + c ^ 2 := by nlinarith
  nlinarith

end Problems.Minif2f.aime_1996_p5
