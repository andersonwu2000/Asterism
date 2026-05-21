import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem tau_deriv_integral_formula
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      derivWithin
        (fun τ' => ∫ t in (0:ℝ)..1, f (H τ' t) * deriv (H τ') t)
        (Set.Icc (0:ℝ) 1) τ
        = f (H τ 1) * derivWithin (fun τ' => H τ' 1) (Set.Icc (0:ℝ) 1) τ
          - f (H τ 0) * derivWithin (fun τ' => H τ' 0) (Set.Icc (0:ℝ) 1) τ := by sorry

end Problems.residue_thm
