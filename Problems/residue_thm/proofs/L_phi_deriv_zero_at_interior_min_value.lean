import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- phi_deriv_zero_at_interior_min_value: Fermat's theorem — interior minimum of φ at value 0
-- forces deriv φ t = 0 via IsLocalMin.deriv_eq_zero; φ ≥ 0 on [0,1] makes φ t = 0 a local min.
-- entry_kind: Builder
theorem phi_deriv_zero_at_interior_min_value
    {φ : ℝ → ℝ}
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (h0 : φ t = 0) :
    deriv φ t = 0 := by
  have hlocalmin : IsLocalMin φ t := by
    rw [IsLocalMin, IsMinFilter]
    have htmem : Set.Ioo (0 : ℝ) 1 ∈ nhds t := Ioo_mem_nhds ht.1 ht.2
    filter_upwards [htmem] with s hs
    have hsicc : s ∈ Set.Icc (0 : ℝ) 1 := Set.Ioo_subset_Icc_self hs
    rw [h0]
    exact (hφrange s hsicc).1
  exact hlocalmin.deriv_eq_zero

end Problems.residue_thm
