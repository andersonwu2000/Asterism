import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem homotopy_to_constant_simply_connected_open
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ (H : ℝ → ℝ → ℂ),
      ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) ∧
      H 0 = γ ∧
      H 1 = (fun _ => γ 0) := by sorry

end Problems.residue_thm
