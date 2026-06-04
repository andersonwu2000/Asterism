import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_re_closed_form_4n2

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce to one closed-form lemma indexed by n ∈ ℕ:
-- Re(∑_{k=1}^{4n+2} k·I^k) = -2n − 2. Apply at n = 24+j (so 98+4j = 4·(24+j)+2)
-- and `push_cast; ring` closes against −50 − 2j.
theorem s9733 : ∀ (j : ℕ),
    (∑ k ∈ Finset.Icc (1 : ℕ) (98 + 4 * j), (↑k : ℂ) * Complex.I ^ k).re
      = -50 - 2 * (j : ℝ)  := by
  intro j
  have hcf := re_closed_form_4n2 (24 + j)
  have heq : 98 + 4 * j = 4 * (24 + j) + 2 := by omega
  rw [heq, hcf]
  push_cast
  ring

end Problems.Minif2f.amc12a_2009_p15
