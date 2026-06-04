import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_chord_zero_left_endpoint
import Problems.Minif2f.amc12b_2021_p21.proofs.L_g_concave_on_icc

namespace Problems.Minif2f.amc12b_2021_p21

-- Concavity-chord decomposition.
-- Define g(z) := 2^√2 · log z − 2^z · log √2. Then g(√2) = 0 by direct
-- computation, and g is concave on [√2, 3] (sub-goal `g_concave_on_icc`).
-- The abstract chord lemma `chord_zero_left_endpoint` (any concave f on
-- [a,b] with f(a)=0) yields (z−a)·f(b) ≤ (b−a)·f(z), specializing to
-- exactly the parent statement with f = g, a = √2, b = 3.
theorem s9807 :
    ∀ z : ℝ, Real.sqrt 2 ≤ z → z ≤ 3 →
      (z - Real.sqrt 2) * ((2:ℝ)^Real.sqrt 2 * Real.log 3
          - (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2))
        ≤ (3 - Real.sqrt 2) * ((2:ℝ)^Real.sqrt 2 * Real.log z
          - (2:ℝ)^z * Real.log (Real.sqrt 2))  := by
  intro z hz_lo hz_hi
  have h_sqrt2_lt_3 : Real.sqrt 2 < 3 := by
    have h9 : Real.sqrt 2 < Real.sqrt 9 := by
      apply Real.sqrt_lt_sqrt (by norm_num); norm_num
    rwa [show (9:ℝ) = 3^2 from by norm_num,
         Real.sqrt_sq (by norm_num : (0:ℝ) ≤ 3)] at h9
  -- Sub-goal 1: concavity of g on [√2, 3].
  have h_concave := g_concave_on_icc
  -- f(√2) = 0 by direct computation.
  have h_zero : (fun z => (2:ℝ)^Real.sqrt 2 * Real.log z
              - (2:ℝ)^z * Real.log (Real.sqrt 2)) (Real.sqrt 2) = 0 := by
    simp only []; ring
  -- Sub-goal 2: abstract chord lemma for concave f with f(a) = 0.
  exact chord_zero_left_endpoint h_sqrt2_lt_3 h_concave h_zero z hz_lo hz_hi

end Problems.Minif2f.amc12b_2021_p21
