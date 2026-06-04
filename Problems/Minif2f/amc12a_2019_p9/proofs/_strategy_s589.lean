import Mathlib
import Problems.Minif2f.amc12a_2019_p9.Defs
import Problems.Minif2f.amc12a_2019_p9.proofs.L_a_at_2019

namespace Problems.Minif2f.amc12a_2019_p9

-- Reduce to the closed-form value of a at n=2019.
-- Reciprocal b n = 1/a n satisfies b(n+2) = 2 b(n+1) - b n (arithmetic progression),
-- giving a n = 3/(4n-1); at n=2019 we get a 2019 = 3/8075,
-- and the den+num arithmetic on 3/8075 closes the goal.
theorem s589 : ∀ (a : ℕ → ℚ) (h₀ : a 1 = 1) (h₁ : a 2 = 3 / 7) (h₂ : ∀ n, a (n + 2) = a n * a (n + 1) / (2 * a n - a (n + 1))), ↑(a 2019).den + (a 2019).num = 8078  := by
  intro a h₀ h₁ h₂
  have h_a2019 : a 2019 = 3 / 8075 := a_at_2019 a h₀ h₁ h₂
  rw [h_a2019]
  native_decide

end Problems.Minif2f.amc12a_2019_p9
