import Mathlib
import Problems.Minif2f.aime_1991_p6.Defs
import Problems.Minif2f.aime_1991_p6.proofs.L_lower_bound_r
import Problems.Minif2f.aime_1991_p6.proofs.L_upper_bound_r

namespace Problems.Minif2f.aime_1991_p6

-- Split the conjunction into lower and upper bound halves; each is structurally
-- simpler (single inequality vs. ∧) and can be tackled independently from h₀.
theorem s9335 : ∀ (r : ℝ), (∑ k ∈ Finset.Icc (19 : ℕ) 91, Int.floor (r + k / 100)) = 546 → (743 : ℝ)/100 ≤ r ∧ r < 744/100  := by
  intro r h₀
  have h_lo := lower_bound_r r h₀
  have h_hi := upper_bound_r r h₀
  exact ⟨h_lo, h_hi⟩

end Problems.Minif2f.aime_1991_p6
