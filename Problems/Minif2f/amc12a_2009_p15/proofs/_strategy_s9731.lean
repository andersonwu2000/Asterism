import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_re_step_4n

namespace Problems.Minif2f.amc12a_2009_p15

-- Induct on n. Base n=0: Icc 1 0 is empty, so sum.re = 0 = 2·0.
-- Step k→k+1: the four extra terms (k₀∈{4k+1,4k+2,4k+3,4k+4}) contribute
-- exactly +2 to the real part (i² = −1, i⁴ = 1; the two real-part terms are
-- −(4k+2)+(4k+4)=2). Encapsulate as one sub-goal `re_step_4n`.
theorem s9731 : ∀ n : ℕ,
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * n), (↑k : ℂ) * Complex.I ^ k).re = 2 * (n : ℝ)  := by
  intro n
  have h_step := re_step_4n
  induction n with
  | zero => simp
  | succ k ih =>
    have h4 : 4 * (k + 1) = 4 * k + 4 := by ring
    rw [h4, h_step k, ih]
    push_cast; ring

end Problems.Minif2f.amc12a_2009_p15
