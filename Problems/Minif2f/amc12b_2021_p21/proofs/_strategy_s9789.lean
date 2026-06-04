import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_g_concave_chord_bound
import Problems.Minif2f.amc12b_2021_p21.proofs.L_g_three_pos

namespace Problems.Minif2f.amc12b_2021_p21

-- Concavity-chord decomposition. Let g(y) := 2^√2 · log y − 2^y · log √2.
-- Then g(√2)=0 (absorbed), g is strictly concave on (0,∞) (g'' < 0), and g(3)>0.
-- By concavity, (3−√2)·g(y) ≥ (y−√2)·g(3) for y ∈ [√2, 3] (chord lower bound).
-- For √2 < y ≤ 3: (y−√2) > 0 and g(3) > 0, so (3−√2)·g(y) > 0, hence g(y) > 0.
theorem s9789 :
    ∀ y : ℝ, 0 < y → Real.sqrt 2 < y → y ≤ 3 →
      (2:ℝ) ^ y * Real.log (Real.sqrt 2) <
        (2:ℝ) ^ Real.sqrt 2 * Real.log y  := by
  intro y hy_pos hy_lo hy_hi
  have h_three_pos : (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2)
      < (2:ℝ)^Real.sqrt 2 * Real.log 3 := g_three_pos
  have h_chord : ∀ z : ℝ, Real.sqrt 2 ≤ z → z ≤ 3 →
      (z - Real.sqrt 2) * ((2:ℝ)^Real.sqrt 2 * Real.log 3
          - (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2))
        ≤ (3 - Real.sqrt 2) * ((2:ℝ)^Real.sqrt 2 * Real.log z
          - (2:ℝ)^z * Real.log (Real.sqrt 2)) := g_concave_chord_bound
  have hy_lo' : Real.sqrt 2 ≤ y := le_of_lt hy_lo
  have h_sqrt2_lt_3 : Real.sqrt 2 < 3 := by
    have : Real.sqrt 2 < Real.sqrt 9 := Real.sqrt_lt_sqrt (by norm_num) (by norm_num)
    rw [show (9:ℝ) = 3^2 from by norm_num, Real.sqrt_sq (by norm_num : (0:ℝ) ≤ 3)] at this
    exact this
  have h_diff_pos : 0 < y - Real.sqrt 2 := by linarith
  have h_three_diff_pos : 0 < 3 - Real.sqrt 2 := by linarith
  have h_g3_pos : 0 < (2:ℝ)^Real.sqrt 2 * Real.log 3
      - (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2) := by linarith
  have h_rhs_pos : 0 < (y - Real.sqrt 2) * ((2:ℝ)^Real.sqrt 2 * Real.log 3
      - (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2)) := mul_pos h_diff_pos h_g3_pos
  have h_lhs_pos : 0 < (3 - Real.sqrt 2) * ((2:ℝ)^Real.sqrt 2 * Real.log y
      - (2:ℝ)^y * Real.log (Real.sqrt 2)) := lt_of_lt_of_le h_rhs_pos (h_chord y hy_lo' hy_hi)
  have h_diff_pos' : 0 < (2:ℝ)^Real.sqrt 2 * Real.log y
      - (2:ℝ)^y * Real.log (Real.sqrt 2) := by
    have := (mul_pos_iff_of_pos_left h_three_diff_pos).mp h_lhs_pos
    exact this
  linarith

end Problems.Minif2f.amc12b_2021_p21
