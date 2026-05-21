import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem integral_split_along_closed_path
    {U : Set ℂ} {T : Finset ℂ} {f g : ℂ → ℂ} {P : ℂ → ℂ → ℂ} {γ : ℝ → ℂ}
    (hg : AnalyticOn ℂ g U)
    (hP_ana : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hpoint : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
      (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) +
      ∑ a ∈ T, ∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t := by sorry

end Problems.residue_thm
