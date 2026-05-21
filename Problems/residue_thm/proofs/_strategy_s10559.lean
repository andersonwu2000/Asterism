import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_int_zero_from_continuous_null_homotopy
import Problems.residue_thm.proofs.L_simply_connected_continuous_null_homotopy_of_loop

namespace Problems.residue_thm

-- Two-step continuous-null-homotopy + discretization, per strategist directive.
-- (1) `simply_connected_continuous_null_homotopy_of_loop`: SimplyConnectedSpace gives a
--     continuous (not C²) null-homotopy H of γ to the constant loop at γ 0, image in U.
-- (2) `path_int_zero_from_continuous_null_homotopy`: given any such continuous null-homotopy
--     of a C¹ closed loop in U (with g analytic on U), ∫ g(γ t)·γ'(t) dt = 0. The discretization
--     argument lives inside this sub-goal (compactness + Lebesgue-number on H([0,1]²) ⊂ U gives
--     a grid where each cell maps to a ball; cell-boundary PL loops are zero by
--     `closed_path_integral_zero_on_ball`; cell sum telescopes to outer rectangle = γ integral).
theorem s10559
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  obtain ⟨H, hHcont, hH0, hH1, hHleft, hHright, hHmaps⟩ :=
    simply_connected_continuous_null_homotopy_of_loop hU hSC hγ hmaps hclosed
  exact path_int_zero_from_continuous_null_homotopy hU hg hγ hmaps hclosed
    H hHcont hH0 hH1 hHleft hHright hHmaps

end Problems.residue_thm
