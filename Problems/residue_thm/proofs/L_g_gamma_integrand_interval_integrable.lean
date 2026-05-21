import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem g_gamma_integrand_interval_integrable
    {U : Set ℂ} {γ : ℝ → ℂ} {g G : ℂ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) U)
    (hG : ∀ z ∈ U, HasDerivAt G (g z) z) :
    IntervalIntegrable (fun t => g (γ t) * deriv γ t) MeasureTheory.volume 0 1 := by sorry

end Problems.residue_thm
