import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_re_dichotomy

set_option maxHeartbeats 0

namespace Problems.Minif2f.amc12a_2009_p15

-- Decompose via dichotomy: for any m > 97, Re(S(m)) is either ≤ -50 or ≥ 50
-- (each 4-step block shifts Re by ±2 from the m=97 value of 48, so Re lands
-- outside the interval (-50, 50) for m ≥ 98). 48 contradicts both branches.
theorem s9596 : ∀ (m : ℕ), 97 < m →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re ≠ 48  := by
  intro m hm habs
  rcases sum_re_dichotomy m hm with h | h
  · linarith
  · linarith

end Problems.Minif2f.amc12a_2009_p15
