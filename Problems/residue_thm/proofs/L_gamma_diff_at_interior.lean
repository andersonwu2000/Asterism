import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- gamma_diff_at_interior: DifferentiableAt from ContDiffOn at interior point via nhds membership
theorem gamma_diff_at_interior
    {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc (0 : ℝ) 1))
    {z : ℝ} (hz : z ∈ Set.Ioo (0 : ℝ) 1) :
    DifferentiableAt ℝ γ z :=
  (hγ.differentiableOn one_ne_zero).differentiableAt
    (Filter.mem_of_superset (isOpen_Ioo.mem_nhds hz) Set.Ioo_subset_Icc_self)

end Problems.residue_thm

