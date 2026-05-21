import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- dw_section_eq_deriv_at_ioo_point: for t in the interior Ioo 0 1, Icc 0 1 ∈ 𝓝 t,
-- so derivWithin (H τ') (Icc 0 1) t = deriv (H τ') t by derivWithin_of_mem_nhds.
theorem dw_section_eq_deriv_at_ioo_point
    {H : ℝ → ℝ → ℂ}
    (_hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (t : ℝ) (ht : t ∈ Set.Ioo (0:ℝ) 1) :
    ∀ τ' ∈ Set.Icc (0:ℝ) 1,
      derivWithin (H τ') (Set.Icc (0:ℝ) 1) t = deriv (H τ') t := by
  intro τ' _
  exact derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)

end Problems.residue_thm
