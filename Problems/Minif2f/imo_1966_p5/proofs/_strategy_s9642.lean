import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs

namespace Problems.Minif2f.imo_1966_p5

-- Direct sorry-free proof of `x 2 = 0` (leaf-bypass — no sub-goals).
-- Strategy: rewrite all abs terms via the ordering a₁>a₂>a₃>a₄, then take two
-- linear combinations of the equations:
--   `h₁₁ - h₁₀` ⇒ (a₂-a₃)·(x₁+x₂-x₃-x₄) = 0 ⇒ x₁+x₂ = x₃+x₄  (divide by a₂-a₃≠0)
--   `h₁₀ - h₉ ` ⇒ (a₁-a₂)·(x₁-x₂-x₃-x₄) = 0 ⇒ x₁ = x₂+x₃+x₄    (divide by a₁-a₂≠0)
-- Substituting the second into the first: 2·x 2 = 0 ⇒ x 2 = 0 (closed by `linarith`).
theorem s9642 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1), x 2 = 0  := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have ha12 : a 1 - a 2 > 0 := by linarith
  have ha13 : a 1 - a 3 > 0 := by linarith
  have ha14 : a 1 - a 4 > 0 := by linarith
  have ha23 : a 2 - a 3 > 0 := by linarith
  have ha24 : a 2 - a 4 > 0 := by linarith
  have ha34 : a 3 - a 4 > 0 := by linarith
  rw [abs_of_pos ha12, abs_of_pos ha13, abs_of_pos ha14] at h₉
  rw [abs_of_neg (by linarith : a 2 - a 1 < 0), abs_of_pos ha23, abs_of_pos ha24] at h₁₀
  rw [abs_of_neg (by linarith : a 3 - a 1 < 0), abs_of_neg (by linarith : a 3 - a 2 < 0), abs_of_pos ha34] at h₁₁
  have hsum_key : (a 2 - a 3) * (x 1 + x 2 - x 3 - x 4) = 0 := by linear_combination h₁₁ - h₁₀
  have hx1_key : (a 1 - a 2) * (x 1 - x 2 - x 3 - x 4) = 0 := by linear_combination h₁₀ - h₉
  have ha23ne : a 2 - a 3 ≠ 0 := by linarith
  have ha12ne : a 1 - a 2 ≠ 0 := by linarith
  have hsum2 : x 1 + x 2 = x 3 + x 4 := by
    rcases mul_eq_zero.mp hsum_key with h | h
    · exact absurd h ha23ne
    · linarith
  have hx1 : x 1 = x 2 + x 3 + x 4 := by
    rcases mul_eq_zero.mp hx1_key with h | h
    · exact absurd h ha12ne
    · linarith
  linarith

end Problems.Minif2f.imo_1966_p5
