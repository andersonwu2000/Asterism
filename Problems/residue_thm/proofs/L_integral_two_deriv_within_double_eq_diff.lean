import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integral_two_deriv_within_double_eq_diff: FTC with linear substitution u=2s on ContDiffOn C¹ path
theorem integral_two_deriv_within_double_eq_diff
    {α' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    {t : ℝ} (ht : t ∈ Set.Icc (0 : ℝ) (1 / 2)) :
    (∫ s in (0 : ℝ)..t, 2 * derivWithin α' (Set.Icc 0 1) (2 * s)) =
        α' (2 * t) - α' 0 := by
  have ht0 : (0 : ℝ) ≤ t := ht.1
  have ht2 : t ≤ 1 / 2 := ht.2
  have key : ∫ s in (0:ℝ)..t, 2 * derivWithin α' (Set.Icc 0 1) (2 * s) =
      (fun s => α' (2 * s)) t - (fun s => α' (2 * s)) 0 := by
    apply intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le ht0
    · have hf : ContinuousOn (fun s : ℝ => 2 * s) (Set.Icc 0 t) :=
        (continuous_const.mul continuous_id').continuousOn.mono (Set.subset_univ _)
      refine ContinuousOn.comp hα'.continuousOn hf ?_
      intro s hs
      simp only [Set.mem_Icc] at hs ⊢
      exact ⟨by linarith, by linarith⟩
    · intro s hs
      have h2s_pos : (0 : ℝ) < 2 * s := by linarith [hs.1]
      have h2s_lt1 : 2 * s < 1 := by linarith [hs.2]
      have hIcc_nhds : Set.Icc 0 1 ∈ nhds (2 * s) := Icc_mem_nhds h2s_pos h2s_lt1
      have hDiff : DifferentiableAt ℝ α' (2 * s) :=
        (hα'.differentiableOn one_ne_zero (2 * s) (Set.mem_Icc.mpr
          ⟨le_of_lt h2s_pos, le_of_lt h2s_lt1⟩)).differentiableAt hIcc_nhds
      have hderiv_eq : derivWithin α' (Set.Icc 0 1) (2 * s) = deriv α' (2 * s) :=
        hDiff.derivWithin (uniqueDiffWithinAt_of_mem_nhds hIcc_nhds)
      rw [hderiv_eq]
      have h_lin : HasDerivAt (fun s => 2 * s) 2 s := by
        simpa using (hasDerivAt_id s).const_mul 2
      have h_comp := hDiff.hasDerivAt.scomp s h_lin
      convert h_comp using 1
    · apply ContinuousOn.intervalIntegrable_of_Icc ht0
      apply ContinuousOn.mul continuousOn_const
      have hf : ContinuousOn (fun s : ℝ => 2 * s) (Set.Icc 0 t) :=
        (continuous_const.mul continuous_id').continuousOn.mono (Set.subset_univ _)
      refine ContinuousOn.comp (hα'.continuousOn_derivWithin
        (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl) hf ?_
      intro s hs
      simp only [Set.mem_Icc] at hs ⊢
      exact ⟨by linarith, by linarith⟩
  simp only [mul_zero, key]

end Problems.residue_thm
