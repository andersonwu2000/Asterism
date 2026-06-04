import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_sum_lower_bound
import Problems.Minif2f.amc12b_2021_p21.proofs.L_sum_upper_bound

namespace Problems.Minif2f.amc12b_2021_p21

-- Split the conjunction; each conjunct becomes an abstract sub-goal over the same (S, h₀).
-- h_lower handles the 2 ≤ sum bound; h_upper handles the sum < 6 bound; combine with And.intro.
theorem s601 : ∀ (S : Finset ℝ) (h₀ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), (↑2 ≤ ∑ k ∈ S, k) ∧ (∑ k ∈ S, k) < 6  := by
  intro S h₀
  have h_lower := sum_lower_bound S h₀
  have h_upper := sum_upper_bound S h₀
  exact ⟨h_lower, h_upper⟩

end Problems.Minif2f.amc12b_2021_p21
