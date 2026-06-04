import Mathlib
import Problems.Minif2f.amc12a_2017_p7.Defs
import Problems.Minif2f.amc12a_2017_p7.proofs.L_odd_value

namespace Problems.Minif2f.amc12a_2017_p7

-- Reduce f(2017) to the closed form for odd inputs: f(2k+1) = 2k+2.
-- Sub-goal `odd_value` proves the general odd-index formula by induction on k;
-- specializing at k = 1008 and simplifying with norm_num closes f 2017 = 2018.
theorem s587 : ∀ (f : ℕ → ℝ) (h₀ : f 1 = 2) (h₁ : ∀ n, 1 < n ∧ Even n → f n = f (n - 1) + 1) (h₂ : ∀ n, 1 < n ∧ Odd n → f n = f (n - 2) + 2), f 2017 = 2018  := by
  intro f h₀ h₁ h₂
  have key := odd_value f h₀ h₁ h₂
  have h := key 1008
  norm_num at h
  exact h

end Problems.Minif2f.amc12a_2017_p7
