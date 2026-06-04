import Mathlib
import Problems.Minif2f.amc12a_2010_p10.Defs

namespace Problems.Minif2f.amc12a_2010_p10

-- Direct proof: substitute p = 5, derive a 0 = 1 from h₀ 0 + h₁ + h₂, then prove the
-- paired statement (a n = 4n+1 ∧ a (n+1) = 4(n+1)+1) by ordinary induction on ℕ; the
-- second-order recurrence h₀ propagates both halves of the pair in one step.
theorem s9350 (p q : ℝ) (a : ℕ → ℝ)
    (h₀ : ∀ n, a (n + 2) - a (n + 1) = a (n + 1) - a n)
    (h₁ : a 1 = p) (h₂ : a 2 = 9)
    (h₃ : a 3 = 3 * p - q) (h₄ : a 4 = 3 * p + q)
    (h_p : p = 5) :
    ∀ n, a n = 4 * (n : ℝ) + 1  := by
  subst h_p
  have h_a0 : a 0 = 1 := by have := h₀ 0; simp at this; linarith
  have h_a1 : a 1 = 5 := h₁
  -- prove paired statement by induction
  have key : ∀ n, a n = 4 * (n : ℝ) + 1 ∧ a (n+1) = 4 * ((n+1) : ℝ) + 1 := by
    intro n
    induction n with
    | zero =>
      refine ⟨?_, ?_⟩
      · simpa using h_a0
      · simp; linarith
    | succ k ih =>
      obtain ⟨ihk, ihk1⟩ := ih
      refine ⟨by push_cast; linarith, ?_⟩
      have hrec := h₀ k
      push_cast
      linarith
  intro n
  exact (key n).1

end Problems.Minif2f.amc12a_2010_p10
