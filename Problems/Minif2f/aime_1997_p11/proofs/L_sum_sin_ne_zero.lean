import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- sum_sin_ne_zero: each sin(nπ/180) > 0 for n∈1..44 (acute angles), so sum is positive
-- open Real in scopes π to Real.pi, avoiding the auto-bound implicit issue
open Real in
theorem sum_sin_ne_zero :
    (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)) ≠ 0 := by
  apply ne_of_gt
  apply Finset.sum_pos
  · intro n hn
    simp only [Finset.mem_Icc] at hn
    apply Real.sin_pos_of_pos_of_lt_pi
    · have h1 : (1 : ℝ) ≤ (n : ℝ) := by exact_mod_cast hn.1
      have hpi : (0 : ℝ) < π := Real.pi_pos
      nlinarith
    · have h2 : (n : ℝ) ≤ 44 := by exact_mod_cast hn.2
      have hpi : (0 : ℝ) < π := Real.pi_pos
      nlinarith
  · exact ⟨1, by simp⟩

end Problems.Minif2f.aime_1997_p11
