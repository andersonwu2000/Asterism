import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_closed_form_im_mod3

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce to one closed-form lemma indexed by n ∈ ℕ:
-- Im(∑_{k=1}^{4n+3} k·I^k) = -2n - 2. Combinator rewrites m = 4·(m/4)+3 and
-- uses 0 ≤ m/4 (cast to ℝ) to bound -2(m/4) - 2 ≤ -2 ≤ 48.
theorem s9722 : ∀ (m : ℕ), 0 < m → m < 97 → m % 4 = 3 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).im ≤ 48  := by
  intro m hpos hlt hmod
  have heq : m = 4 * (m / 4) + 3 := by omega
  have hcf := closed_form_im_mod3
  rw [heq, hcf]
  have hcast : (0 : ℝ) ≤ ((m / 4 : ℕ) : ℝ) := by exact_mod_cast Nat.zero_le _
  linarith

end Problems.Minif2f.amc12a_2009_p15
