import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_path_int_zero_given_ball_cover
import Problems.residue_thm.proofs.L_ball_cover_along_path_exists

namespace Problems.residue_thm

-- Ball-cover subdivision (per strategist directive): extract a finite ball
-- cover of γ([0,1]) ⊆ U, then collapse the integral via per-ball Cauchy +
-- telescoping primitives. Sub-goal (1) is pure topology (compactness of γ([0,1])
-- + Lebesgue-number lemma on the cover by Mathlib.Metric.IsOpen.mem_nhds); (2)
-- packages the analytic monodromy/telescope step given the cover, citing the
-- proved `closed_path_integral_zero_on_ball` (s10400) via a primitive on each
-- ball and a telescoping cancellation under `γ 0 = γ 1`.
theorem s10491
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  obtain ⟨n, t, c, r, ht0, htn, hmono, hpos, hball, hseg⟩ :=
    ball_cover_along_path_exists hU hγ hmaps
  exact analytic_path_int_zero_given_ball_cover hU hg hγ hmaps hclosed
    ht0 htn hmono hpos hball hseg


end Problems.residue_thm

