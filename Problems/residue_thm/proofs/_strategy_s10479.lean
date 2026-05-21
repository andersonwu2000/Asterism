import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_null_homotopy_loop_integral_eq
import Problems.residue_thm.proofs.L_homotopy_invariance_wrap
import Problems.residue_thm.proofs.L_path_integral_const_loop_zero

namespace Problems.residue_thm

-- Bypass the C¹/C² obstruction (LESSONS line 34) by routing through a C² null-homotopy
-- whose 0-slice has integral equal to (but not pointwise equal to) the integral over γ.
-- Then homotopy_invariant_contour_integral (s10331) reduces to the constant-slice integral.
-- Sub-goals:
--  (1) `c2_null_homotopy_loop_integral_eq` (Backward) — construct a C² homotopy H from a
--      loop with integral equal to ∫ over γ, to a constant, all inside U.
--  (2) `path_integral_const_loop_zero` (Builder) — for a constant path, the integrand
--      g(c) * deriv (const) t is g(c) * 0 = 0, so the integral is 0.
--  (3) `homotopy_invariance_wrap` (Builder, leaf wrapper) — re-exports proved sibling
--      `homotopy_invariant_contour_integral` (s10331) so the framework auto-imports it
--      (per LESSONS line 26: direct citation of proved siblings fails lake build).
-- Combinator: chain integral equality → homotopy invariance → constant-loop zero.
theorem s10479
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  have h_homotopy :=
    c2_null_homotopy_loop_integral_eq hU hSC hg hγ hmaps hclosed
  have h_const := path_integral_const_loop_zero g (γ 0)
  obtain ⟨H, hC2, hMaps, hH0, hH1, hConst, hEq⟩ := h_homotopy
  have h_inv := homotopy_invariance_wrap hU hg hC2 hMaps hH0 hH1
  rw [← hEq, h_inv, hConst]
  exact h_const
end Problems.residue_thm
