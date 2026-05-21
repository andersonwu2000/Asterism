import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_integral_eq_primitive_diff
import Problems.residue_thm.proofs.L_primitive_exists_on_simply_connected

namespace Problems.residue_thm

-- Existence of primitive on simply-connected open `U` (sub-goal 1, analytic core)
-- + FTC along the C¹ path (sub-goal 2, calculus) ⇒ `∫_γ f = F(γ 1) - F(γ 0) = 0`
-- via closed-path hypothesis.
theorem s10317
    {U : Set ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hSC : SimplyConnectedSpace U)
    (hf : AnalyticOn ℂ f U)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U)
    (hγcl : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 0  := by
  have h_prim := primitive_exists_on_simply_connected hU hSC hf
  obtain ⟨F, hF⟩ := h_prim
  have h_ftc := path_integral_eq_primitive_diff hU hF hγC1 hγU
  rw [h_ftc, hγcl, sub_self]


end Problems.residue_thm
