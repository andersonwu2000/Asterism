import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_re_closed_form_4n1

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce to one closed-form lemma indexed by n ∈ ℕ:
-- Re(∑_{k=1}^{4n+1} k·I^k) = 2n. Combinator rewrites m = 4·(m/4)+1 and
-- closes by `push_cast; ring` against the parent RHS ((m-1)/2).
theorem s9732 : ∀ (m : ℕ), 0 < m → m % 4 = 1 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re = ((m : ℝ) - 1) / 2  := by
  intro m hpos hmod
  have heq : m = 4 * (m / 4) + 1 := by omega
  have hcf := re_closed_form_4n1 (m / 4)
  rw [heq, hcf]
  push_cast
  ring

end Problems.Minif2f.amc12a_2009_p15
