import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_remainder_principal_part_decomp

namespace Problems.residue_thm

-- principal_part_split_wrapper: wrapper re-exporting analytic_remainder_principal_part_decomp (s10453)
theorem principal_part_split_wrapper
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a})) ∧
      (∀ a ∈ T, Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0)) ∧
      (∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a) ∧
      (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
        (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) +
        ∑ a ∈ T, ∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t := by
  exact analytic_remainder_principal_part_decomp hU hT hf hγ hmaps

end Problems.residue_thm

