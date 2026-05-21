import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- gamma_lipschitz_on_unit_icc: C¹ on compact convex Icc 0 1 implies Lipschitz via
-- ContDiffOn.exists_lipschitzOnWith (convex_Icc + isCompact_Icc).
theorem gamma_lipschitz_on_unit_icc
    {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc (0 : ℝ) 1)) :
    ∃ K : NNReal, LipschitzOnWith K γ (Set.Icc (0 : ℝ) 1) :=
  hγ.exists_lipschitzOnWith one_ne_zero (convex_Icc 0 1) isCompact_Icc

end Problems.residue_thm
