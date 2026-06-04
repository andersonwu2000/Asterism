import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs.L_vieta_descent_le

namespace Problems.Minif2f.imo_1988_p6

-- WLOG reduction: a' ^ 2 + b' ^ 2 and a' * b' are symmetric in (a', b'); swap on
-- a' ≤ b' lets us assume b ≤ a, which is the precondition the descent argument needs.
-- vieta_descent_le carries the substantive Vieta-jumping descent under that order.
theorem s9449 : ∀ (a' b' k' : ℕ), 0 < a' → 0 < b' →
    a' ^ 2 + b' ^ 2 = (a' * b' + 1) * k' → ∃ x : ℕ, x ^ 2 = k'  := by
  intro a' b' k' ha hb heq
  rcases le_total b' a' with hba | hba
  · exact vieta_descent_le a' b' k' ha hb hba heq
  · refine vieta_descent_le b' a' k' hb ha hba ?_
    rw [add_comm, mul_comm b' a']
    exact heq

end Problems.Minif2f.imo_1988_p6
