import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- polar_path_smooth: ContDiffOn ℝ 1 for the polar interpolation path t ↦ (1-t+t‖w‖)·exp(it·arg w)
-- Proof: split as ContDiffOn.mul; the real-linear factor uses ofRealCLM.contDiff; the exp factor
-- uses ContDiffOn.cexp composed with the linear map ofReal ∘ (t ↦ t·arg w) and const I.
theorem polar_path_smooth (w : ℂ) (_hw : w ≠ 0) :
    ContDiffOn ℝ 1 (fun t : ℝ =>
        (((1 - t + t * ‖w‖ : ℝ) : ℂ)) *
          Complex.exp (((t * Complex.arg w : ℝ) : ℂ) * Complex.I))
      (Set.Icc 0 1) := by
  apply ContDiffOn.mul
  · have h1 : ContDiffOn ℝ 1 (fun t : ℝ => (1 - t + t * ‖w‖ : ℝ)) (Set.Icc 0 1) := by fun_prop
    have h2 : ContDiffOn ℝ 1 (Complex.ofReal : ℝ → ℂ) Set.univ :=
      Complex.ofRealCLM.contDiff.contDiffOn
    exact h2.comp h1 (fun _ _ => Set.mem_univ _)
  · apply ContDiffOn.cexp
    apply ContDiffOn.mul
    · have h1 : ContDiffOn ℝ 1 (fun t : ℝ => (t * Complex.arg w : ℝ)) (Set.Icc 0 1) := by
        fun_prop
      have h2 : ContDiffOn ℝ 1 (Complex.ofReal : ℝ → ℂ) Set.univ :=
        Complex.ofRealCLM.contDiff.contDiffOn
      exact h2.comp h1 (fun _ _ => Set.mem_univ _)
    · exact contDiffOn_const
end Problems.residue_thm
