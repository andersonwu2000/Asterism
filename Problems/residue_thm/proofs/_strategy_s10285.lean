import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_integral_simply_connected_zero
import Problems.residue_thm.proofs.L_holomorphic_extension_subtract_poles

namespace Problems.residue_thm

-- The corrected integrand `f - ∑ residue/(z-a)` extends to an analytic function `g` on all of `U`
-- (residues cancel poles ⇒ removable singularities). For closed C¹ curves in simply-connected `U`,
-- the integral of any analytic function vanishes (Cauchy). Combining: rewrite via the extension's
-- equality on `U \ T` (which γ maps into) and invoke Cauchy on `g`.
theorem s10285
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0 : ℝ)..1,
      (f (γ t) - ∑ a ∈ T, Complex.residue f a / (γ t - a)) * deriv γ t) = 0  := by
  obtain ⟨g, hg_anal, hg_eq⟩ :=
    holomorphic_extension_subtract_poles hU hT hf
  have h_eq : Set.EqOn
      (fun t => (f (γ t) - ∑ a ∈ T, Complex.residue f a / (γ t - a)) * deriv γ t)
      (fun t => g (γ t) * deriv γ t)
      (Set.uIcc (0:ℝ) 1) := by
    intro t ht
    have ht' : t ∈ Set.Icc (0:ℝ) 1 := by
      simpa [Set.uIcc_of_le (zero_le_one)] using ht
    have hγt : γ t ∈ U \ ↑T := hmap ht'
    simp [hg_eq (γ t) hγt]
  rw [intervalIntegral.integral_congr h_eq]
  exact cauchy_integral_simply_connected_zero
    hU hsc hT hf hγ hmap hclosed hg_anal

end Problems.residue_thm
