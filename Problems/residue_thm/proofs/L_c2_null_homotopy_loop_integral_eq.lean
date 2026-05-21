import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem c2_null_homotopy_loop_integral_eq
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ (H : ℝ → ℝ → ℂ),
      ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) ∧
      H 1 = (fun _ => γ 0) ∧
      (∫ t in (0:ℝ)..1, g (H 0 t) * deriv (H 0) t)
        = (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) := by sorry

end Problems.residue_thm
