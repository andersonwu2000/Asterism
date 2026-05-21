import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10409

namespace Problems.residue_thm

-- principal_part_at_singularity_step_wrapper: wrapper forwarding to the proved
-- principal_part_extraction_at_singularity toolkit (s10409); gives the Laurent-type
-- P+g decomposition of f on a punctured ball at an isolated singularity.
theorem principal_part_at_singularity_step_wrapper
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (P g : ℂ → ℂ),
      AnalyticOn ℂ P (Set.univ \ {z₀}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ g (Metric.ball z₀ R) ∧
      ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z := by
  exact s10409 hR hf

end Problems.residue_thm

