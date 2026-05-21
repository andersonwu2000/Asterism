import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_closed_path_zero_from_punctured_primitive
import Problems.residue_thm.proofs.L_punctured_primitive_subtracted

namespace Problems.residue_thm

-- Q := P − r/(·−a) (r := residue P a) is analytic on ℂ\{a} with residue 0 at a,
-- so the parent contour integral collapses by FTC once a primitive of Q on ℂ\{a}
-- exists. Sub-goal (1) `punctured_primitive_subtracted` (Backward) builds that
-- primitive (carries the analytic content: Laurent decay of P at a + entire
-- antiderivative of the negative-Laurent tail). Sub-goal (2)
-- `closed_path_zero_from_punctured_primitive` (Builder) is the FTC closer:
-- given primitive F on ℂ\{a}, γ closed C¹ in ℂ\{a}, applies
-- `path_integral_eq_primitive_diff` (proved sibling on the open set ℂ\{a}) to
-- get F(γ 1) − F(γ 0), then `hclosed` collapses to 0.
theorem s10478
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, (P (γ t) - Complex.residue P a / (γ t - a)) * deriv γ t) = 0  := by
  have h_prim :=
    punctured_primitive_subtracted hP hP_tendsto hγ h_avoid hclosed
  obtain ⟨F, hF⟩ := h_prim
  exact closed_path_zero_from_punctured_primitive
    (F := F) hP hP_tendsto hγ h_avoid hclosed hF

end Problems.residue_thm
