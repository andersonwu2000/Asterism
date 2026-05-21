import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- path_reverse_c1: ContDiffOn of β∘(1-·) via ContDiffOn.comp with the affine reversal map
theorem path_reverse_c1
    {β : ℝ → ℂ}
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1)) :
    ContDiffOn ℝ 1 (fun t => β (1 - t)) (Set.Icc 0 1) := by
  have hg : ContDiffOn ℝ 1 (fun t : ℝ => 1 - t) (Set.Icc 0 1) :=
    (contDiffOn_const.sub contDiffOn_id)
  have hmaps : Set.MapsTo (fun t : ℝ => 1 - t) (Set.Icc 0 1) (Set.Icc 0 1) := by
    intro t ht
    simp only [Set.mem_Icc] at ht ⊢
    constructor <;> linarith [ht.1, ht.2]
  exact hβ.comp hg hmaps

end Problems.residue_thm
