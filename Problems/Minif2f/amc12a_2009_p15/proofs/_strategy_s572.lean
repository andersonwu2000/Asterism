import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_at_97
import Problems.Minif2f.amc12a_2009_p15.proofs.L_unique_at_97

namespace Problems.Minif2f.amc12a_2009_p15

-- Decompose into (i) closed-form value at n = 97, and (ii) uniqueness of the n
-- yielding the same partial sum. Combine via transitivity: h₁ : S(n) = 48+49i and
-- h_at_97 : S(97) = 48+49i give S(n) = S(97), so uniqueness forces n = 97.
theorem s572 : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : (∑ k ∈ Finset.Icc 1 n, ↑k * Complex.I ^ k) = 48 + 49 * Complex.I), n = 97 := by
  intro n h₀ h₁
  have h_at_97 := at_97
  exact unique_at_97 n h₀ (h₁.trans h_at_97.symm)

end Problems.Minif2f.amc12a_2009_p15
