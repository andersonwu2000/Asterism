import Mathlib
import Problems.Minif2f.induction_sum_odd.Defs

namespace Problems.Minif2f.induction_sum_odd

-- Direct proof: induction on n.
-- Base: empty sum = 0 = 0^2. Step: ∑_{k<n+1} (2k+1) = ∑_{k<n} (2k+1) + (2n+1)
-- = n^2 + 2n + 1 = (n+1)^2 by ring.
theorem s629 : ∀ (n : ℕ), (∑ k ∈ Finset.range n, (2 * k + 1)) = n ^ 2  := by
  intro n
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, ih]
    ring

end Problems.Minif2f.induction_sum_odd
