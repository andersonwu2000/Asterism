import Mathlib
import Problems.Minif2f.amc12a_2019_p9.Defs
import Problems.Minif2f.amc12a_2019_p9.proofs.L_base_one
import Problems.Minif2f.amc12a_2019_p9.proofs.L_base_two
import Problems.Minif2f.amc12a_2019_p9.proofs.L_induction_step

namespace Problems.Minif2f.amc12a_2019_p9

-- Decompose closed-form proof into two base cases + an inductive step.
-- base_one/base_two pin a 1, a 2 to the closed form (h₀/h₁ are literal).
-- induction_step is the algebraic core: given the closed form at k+1 and k+2,
-- derive it at k+3 via the recurrence h₂ (k+1).
-- Combinator: bundle (a (k+1), a (k+2)) into a pair invariant, prove by Nat
-- induction (zero ↦ ⟨base_one, base_two⟩; succ ↦ slide window via induction_step),
-- then extract `a n` for `n = m+1` (n ≥ 1 ⇒ ∃ m, n = m+1).
theorem s9355 : ∀ (a : ℕ → ℚ) (h₀ : a 1 = 1) (h₁ : a 2 = 3 / 7)
    (h₂ : ∀ n, a (n + 2) = a n * a (n + 1) / (2 * a n - a (n + 1)))
    (n : ℕ), 1 ≤ n → a n = 3 / (4 * (n : ℚ) - 1)  := by
  intro a h₀ h₁ h₂ n hn
  have h_base1 := base_one a h₀ h₁ h₂
  have h_base2 := base_two a h₀ h₁ h₂
  have h_step := induction_step a h₀ h₁ h₂
  have key : ∀ k : ℕ, a (k+1) = 3 / (4 * ((k+1:ℕ):ℚ) - 1) ∧
      a (k+2) = 3 / (4 * ((k+2:ℕ):ℚ) - 1) := by
    intro k
    induction k with
    | zero => exact ⟨h_base1, h_base2⟩
    | succ j ih => exact ⟨ih.2, h_step j ih.1 ih.2⟩
  obtain ⟨m, rfl⟩ : ∃ m, n = m + 1 := ⟨n - 1, by omega⟩
  exact (key m).1

end Problems.Minif2f.amc12a_2019_p9
