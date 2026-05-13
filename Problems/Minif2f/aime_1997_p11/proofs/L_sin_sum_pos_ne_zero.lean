import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- sin_sum_pos_ne_zero: sum of sin(n°) for n=1..44 is positive (all terms sin_pos_of_pos_of_lt_pi)
-- Each term: n*π/180 ∈ (0,π) since 1 ≤ n ≤ 44 < 180, so sin > 0 and the sum is positive.
open Real in
set_option linter.style.longLine false in
theorem sin_sum_pos_ne_zero :
    (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)) ≠ 0 := by
  apply _root_.ne_of_gt
  apply Finset.sum_pos
  · intro n hn
    simp only [Finset.mem_Icc] at hn
    apply Real.sin_pos_of_pos_of_lt_pi
    · have h1 : (1 : ℝ) ≤ (n : ℝ) := by exact_mod_cast hn.1
      have hpi : (0 : ℝ) < π := Real.pi_pos
      positivity
    · have h2 : (n : ℝ) ≤ 44 := by exact_mod_cast hn.2
      have hpi : (0 : ℝ) < π := Real.pi_pos
      nlinarith
  · simp [Finset.nonempty_Icc]

end Problems.Minif2f.aime_1997_p11
