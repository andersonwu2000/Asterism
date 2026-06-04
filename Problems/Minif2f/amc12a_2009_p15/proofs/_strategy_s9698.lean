import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_re_closed_form_4n3

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce to a single closed-form lemma indexed by n ∈ ℕ:
-- Re(∑_{k=1}^{4n+3} k·I^k) = -2(n+1). Combinator rewrites m = 4·(m/4)+3 and
-- uses 97 < m ∧ m%4=3 ⇒ m/4 ≥ 24 to bound -2((m/4)+1) ≤ -50.
theorem s9698 : ∀ (m : ℕ), 97 < m → m % 4 = 3 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re ≤ -50  := by
  intro m hm hmod
  have heq : m = 4 * (m / 4) + 3 := by omega
  have hge : 24 ≤ m / 4 := by omega
  have hcf := re_closed_form_4n3 (m / 4)
  rw [heq, hcf]
  have hcast : ((m / 4 : ℕ) : ℝ) ≥ 24 := by exact_mod_cast hge
  linarith

end Problems.Minif2f.amc12a_2009_p15
