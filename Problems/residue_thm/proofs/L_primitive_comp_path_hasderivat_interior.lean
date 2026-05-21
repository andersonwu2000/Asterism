import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- primitive_comp_path_hasderivat_interior: chain rule (HasDerivAt F at γ x, HasDerivAt γ at x)
-- Interior x ∈ Ioo gives Icc ∈ nhds x, upgrading ContDiffOn to DifferentiableAt.
set_option linter.unusedVariables false in
theorem primitive_comp_path_hasderivat_interior
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc a b))
    (hγU : Set.MapsTo γ (Set.Icc a b) (Metric.ball z₀ R)) :
    ∀ x ∈ Set.Ioo a b,
      HasDerivAt (fun s => F (γ s)) (f (γ x) * deriv γ x) x := by
  intro x hx
  have hx_mem : x ∈ Set.Icc a b := Set.mem_Icc_of_Ioo hx
  have hγx : γ x ∈ Metric.ball z₀ R := hγU hx_mem
  have hFγx : HasDerivAt F (f (γ x)) (γ x) := hF (γ x) hγx
  have hIcc_nhds : Set.Icc a b ∈ nhds x := Icc_mem_nhds hx.1 hx.2
  have hγDA : DifferentiableAt ℝ γ x :=
    (hγ.differentiableOn one_ne_zero x hx_mem).differentiableAt hIcc_nhds
  have hγHA : HasDerivAt γ (deriv γ x) x := hγDA.hasDerivAt
  exact hFγx.comp x hγHA

end Problems.residue_thm
