import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- phi_deriv_zero_alias: IsLocalMin/Max at boundary image ⇒ deriv = 0
-- If φ maps Icc 0 1 into itself and φ t ∈ {0, 1} for interior t,
-- then φ attains a local extremum at t, so deriv φ t = 0.
theorem phi_deriv_zero_alias
    {φ : ℝ → ℝ}
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (hbnd : φ t = 0 ∨ φ t = 1) :
    deriv φ t = 0 := by
  have _ := hφmono
  have hdiff : DifferentiableAt ℝ φ t := hφ.differentiable one_ne_zero t
  rcases hbnd with h | h
  · -- φ t = 0: local minimum
    have hmin : IsLocalMin φ t := by
      apply Filter.Eventually.mono (Ioo_mem_nhds ht.1 ht.2)
      intro s hs
      have hsc := (hφrange s (Set.Ioo_subset_Icc_self hs)).1
      linarith [h.symm.le]
    exact hmin.hasDerivAt_eq_zero hdiff.hasDerivAt
  · -- φ t = 1: local maximum
    have hmax : IsLocalMax φ t := by
      apply Filter.Eventually.mono (Ioo_mem_nhds ht.1 ht.2)
      intro s hs
      have hsc := (hφrange s (Set.Ioo_subset_Icc_self hs)).2
      linarith [h.symm.le]
    exact hmax.hasDerivAt_eq_zero hdiff.hasDerivAt

end Problems.residue_thm
