import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_eq_endpoint_diff_via_primitive
import Problems.residue_thm.proofs.L_primitive_exists_on_simply_connected

namespace Problems.residue_thm

-- Cauchy: on simply-connected open `U`, an analytic `g` has a primitive `G`
-- (`primitive_exists_on_simply_connected`); FTC + chain rule then gives the
-- integral along any C¹ curve in `U` as `G(γ 1) - G(γ 0)`
-- (`integral_eq_endpoint_diff_via_primitive`); closed loop ⇒ difference is zero.
theorem s10288
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    {g : ℂ → ℂ} (hg : AnalyticOn ℂ g U) :
    (∫ t in (0 : ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  have h_prim : ∃ G : ℂ → ℂ, ∀ z ∈ U, HasDerivAt G (g z) z :=
    primitive_exists_on_simply_connected hU hsc hg
  obtain ⟨G, hG⟩ := h_prim
  have hmapU : Set.MapsTo γ (Set.Icc 0 1) U :=
    hmap.mono_right Set.diff_subset
  have h_int_eq :
      (∫ t in (0 : ℝ)..1, g (γ t) * deriv γ t) = G (γ 1) - G (γ 0) :=
    integral_eq_endpoint_diff_via_primitive hγ hmapU hG
  rw [h_int_eq, hclosed, sub_self]

end Problems.residue_thm
