import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- c1_reversed_path: ContDiffOn of reversed path via composition with (1 - ·)
theorem c1_reversed_path
    {β : ℝ → ℂ}
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1)) :
    ContDiffOn ℝ 1 (fun t => β (1 - t)) (Set.Icc 0 1) := by
  have h1 : ContDiffOn ℝ 1 (fun t : ℝ => 1 - t) (Set.Icc 0 1) :=
    (contDiff_const.sub contDiff_id).contDiffOn
  have h2 : Set.MapsTo (fun t : ℝ => 1 - t) (Set.Icc 0 1) (Set.Icc 0 1) := by
    intro t ht
    simp only [Set.mem_Icc] at ht ⊢
    constructor <;> linarith [ht.1, ht.2]
  exact hβ.comp h1 h2

end Problems.residue_thm

