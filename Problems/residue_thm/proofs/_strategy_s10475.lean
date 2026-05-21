import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_zero_from_closed_primitive_ftc
import Problems.residue_thm.proofs.L_integrand_intvl_integrable_wrapper
import Problems.residue_thm.proofs.L_primitive_along_closed_path_simply_connected

namespace Problems.residue_thm

-- Factor through a primitive of the integrand along γ. For g analytic on a
-- simply-connected open U and closed C¹ γ in U, build F : ℝ → ℂ continuous on
-- [0,1] with derivative g(γ t)·γ'(t) on the open interval and F 0 = F 1 (this
-- is where simple-connectedness enters — monodromy of local primitives glued
-- along the path). Then FTC collapses the integral to F 1 − F 0 = 0.
-- Sub-goals:
--  (1) `integrand_intvl_integrable_wrapper` (Builder, leaf wrapper) — exposes
--      the proved sibling `intvl_integrable_continuous_circ_c1` so the
--      strategy file can use the integrability via auto-import.
--  (2) `primitive_along_closed_path_simply_connected` (Backward) — primitive
--      existence + closed endpoints in simply-connected open. All analytic /
--      topological content is here.
--  (3) `integral_zero_from_closed_primitive_ftc` (Builder) — pure FTC closer:
--      given the primitive and integrability, ∫ = F 1 − F 0 = 0.
theorem s10475
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  have h_int := integrand_intvl_integrable_wrapper (g := g) (γ := γ) hg hγ hmaps
  obtain ⟨F, hF_cont, hF_deriv, hF_closed⟩ :=
    primitive_along_closed_path_simply_connected hU hSC hg hγ hmaps hclosed
  exact integral_zero_from_closed_primitive_ftc (g := g) (γ := γ) (F := F)
    hF_cont hF_deriv hF_closed h_int

end Problems.residue_thm
