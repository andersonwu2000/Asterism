import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- right_integrand_cont_on_icc: ContinuousOn of 2·derivWithin β'(Icc 0 1)(2s-1) on Icc(1/2,1)
-- via ContDiffOn.continuousOn_derivWithin composed with the linear reparametrization s↦2s-1
theorem right_integrand_cont_on_icc {β' : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ContinuousOn (fun s : ℝ => 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      (Set.Icc (1/2 : ℝ) 1) := by
  have hderiv : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hmap : Set.MapsTo (fun s : ℝ => 2*s - 1) (Set.Icc (1/2 : ℝ) 1) (Set.Icc 0 1) := by
    intro s hs
    simp only [Set.mem_Icc] at hs ⊢
    constructor <;> linarith [hs.1, hs.2]
  have hlin : ContinuousOn (fun s : ℝ => 2*s - 1) (Set.Icc (1/2 : ℝ) 1) :=
    ((continuous_const.mul continuous_id).sub continuous_const).continuousOn
  exact continuousOn_const.mul (hderiv.comp hlin hmap)

end Problems.residue_thm
