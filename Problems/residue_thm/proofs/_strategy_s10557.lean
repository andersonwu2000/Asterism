import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_q_uniform_smallness_on_unit_segment
import Problems.residue_thm.proofs.L_tendsto_segment_integral_from_uniform_smallness

namespace Problems.residue_thm

-- Decompose `∫ Q (z + t·h) dt → Q z` as h → 0 into:
-- (1) `q_uniform_smallness_on_unit_segment`: from `ContinuousAt Q z`,
--     ∀ ε>0, eventually-in-h `‖Q (z + t·h) - Q z‖ ≤ ε` uniformly in t ∈ [0,1]
--     (continuity + compactness/boundedness of the segment {t·h : t ∈ [0,1]}).
-- (2) `tendsto_segment_integral_from_uniform_smallness`: integral squeeze
--     `‖∫ (Q(z+t·h) - Q z) dt‖ ≤ ε`, combined with `∫ Q z dt = Q z`, gives the tendsto.
theorem s10557
    (Q : ℂ → ℂ) (z : ℂ) (h_cont : ContinuousAt Q z) :
    Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))  := by
  have h_unif := q_uniform_smallness_on_unit_segment Q z h_cont
  exact tendsto_segment_integral_from_uniform_smallness Q z h_unif

end Problems.residue_thm
