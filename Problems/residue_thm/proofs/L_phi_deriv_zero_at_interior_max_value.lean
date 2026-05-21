import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- phi_deriv_zero_at_interior_max_value: Fermat's theorem — φ hits max value 1 at
-- interior point t, so it is a local max, hence deriv φ t = 0.
theorem phi_deriv_zero_at_interior_max_value
    {φ : ℝ → ℝ}
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (h1 : φ t = 1) :
    deriv φ t = 0 := by
  have hmax : IsLocalMax φ t := by
    apply Filter.Eventually.mono (Ioo_mem_nhds ht.1 ht.2)
    intro s hs
    have hs' : s ∈ Set.Icc (0 : ℝ) 1 := Set.Ioo_subset_Icc_self hs
    have : φ s ≤ 1 := (hφrange s hs').2
    linarith [h1.symm ▸ le_refl (φ t)]
  exact hmax.deriv_eq_zero

end Problems.residue_thm
