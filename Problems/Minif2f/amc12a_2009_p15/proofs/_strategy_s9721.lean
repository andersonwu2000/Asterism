import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_im_closed_form_4n2

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce to single closed-form lemma indexed by n ∈ ℕ:
-- Im(∑_{k=1}^{4n+2} k·I^k) = 2n+1. Combinator rewrites m = 4·(m/4)+2 and
-- uses 0 < m ∧ m < 97 ∧ m%4=2 ⇒ m/4 ≤ 23 to bound 2((m/4))+1 ≤ 47 ≤ 48.
theorem s9721 : ∀ (m : ℕ), 0 < m → m < 97 → m % 4 = 2 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).im ≤ 48  := by
  intro m hpos hm hmod
  have heq : m = 4 * (m / 4) + 2 := by omega
  have hle : m / 4 ≤ 23 := by omega
  have hcf := im_closed_form_4n2
  rw [heq, hcf]
  have hcast : ((m / 4 : ℕ) : ℝ) ≤ 23 := by exact_mod_cast hle
  linarith

end Problems.Minif2f.amc12a_2009_p15
