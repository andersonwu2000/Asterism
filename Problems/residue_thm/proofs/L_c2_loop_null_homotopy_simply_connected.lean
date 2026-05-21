import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem c2_loop_null_homotopy_simply_connected
    {U : Set ℂ} {η : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hηC2 : ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1))
    (hηMaps : Set.MapsTo η (Set.Icc (0:ℝ) 1) U)
    (hηclosed : η 0 = η 1) :
    ∃ (H : ℝ → ℝ → ℂ),
      ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) ∧
      H 0 = η ∧
      H 1 = (fun _ => η 0) := by sorry

end Problems.residue_thm
