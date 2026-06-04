import Mathlib
import Problems.Minif2f.amc12a_2009_p25.proofs.L_induction_step

namespace Problems.Minif2f.amc12a_2009_p25

-- Two-step induction on n via a paired invariant
--   P(n) := a(n+24) = a n  ∧  a(n+1+24) = a(n+1)
-- Bases P(1) come from h_25 and h_26; the successor step relies on the
-- single sub-goal `induction_step`, the pure algebraic chase
--   a((n+2)+24) = a(n+2) from a(n+24)=a n and a(n+1+24)=a(n+1)
-- using the recurrence h₂. Splitting off `induction_step` removes the
-- universal quantifier and h₀, h₁ from the leaf — strictly simpler.
theorem s9950 :
    ∀ (a : ℕ → ℝ) (h₀ : a 1 = 1) (h₁ : a 2 = 1 / Real.sqrt 3)
      (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1)))
      (h_25 : a 25 = a 1) (h_26 : a 26 = a 2),
      ∀ n, 1 ≤ n → a (n + 24) = a n  := by
  intro a h₀ h₁ h₂ h_25 h_26
  have h_induction_step := induction_step a h₂
  suffices hpair : ∀ n, 1 ≤ n → a (n + 24) = a n ∧ a (n + 1 + 24) = a (n + 1) by
    intro n hn
    exact (hpair n hn).1
  intro n hn
  induction n, hn using Nat.le_induction with
  | base =>
    refine ⟨?_, ?_⟩
    · show a (1 + 24) = a 1; exact h_25
    · show a (1 + 1 + 24) = a (1 + 1); exact h_26
  | succ m hm ih =>
    obtain ⟨ih1, ih2⟩ := ih
    refine ⟨ih2, ?_⟩
    exact h_induction_step m hm ih1 ih2

end Problems.Minif2f.amc12a_2009_p25
