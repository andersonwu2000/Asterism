import Mathlib
import Problems.Minif2f.amc12a_2002_p12.Defs
import Problems.Minif2f.amc12a_2002_p12.proofs.L_pair_is_2_or_61

namespace Problems.Minif2f.amc12a_2002_p12

-- Decompose: Vieta gives a+b=63 (odd ⇒ one of a,b is the even prime 2; other is 61).
-- Sub-goal `pair_is_2_or_61` ships the primality/Vieta case analysis as a disjunction;
-- combinator dispatches each branch by substituting and computing k from f a = 0.
theorem s527 : ∀ (f : ℝ → ℝ) (k : ℝ) (a b : ℕ) (h₀ : ∀ x, f x = x ^ 2 - 63 * x + k)
    (h₁ : f a = 0 ∧ f b = 0) (h₂ : a ≠ b) (h₃ : Nat.Prime a ∧ Nat.Prime b), k = 122 := by
  intro f k a b h₀ h₁ h₂ h₃
  have h_pair : (a = 2 ∧ b = 61) ∨ (a = 61 ∧ b = 2) :=
    pair_is_2_or_61 f k a b h₀ h₁ h₂ h₃
  rcases h_pair with ⟨ha, _⟩ | ⟨ha, _⟩
  · have hfa : f a = 0 := h₁.1
    rw [h₀] at hfa
    subst ha
    push_cast at hfa
    linarith
  · have hfa : f a = 0 := h₁.1
    rw [h₀] at hfa
    subst ha
    push_cast at hfa
    linarith

end Problems.Minif2f.amc12a_2002_p12
