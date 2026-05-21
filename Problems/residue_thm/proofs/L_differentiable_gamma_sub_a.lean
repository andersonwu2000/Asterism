import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem differentiable_gamma_sub_a
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1)) :
    DifferentiableOn ℝ
      (fun s => γ s - a)
      (Set.Icc (0:ℝ) 1) := by fun_prop

end Problems.residue_thm
