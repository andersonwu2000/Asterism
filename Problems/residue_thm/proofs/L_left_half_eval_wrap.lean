import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- left_half_eval_wrap: FTC via scomp chain rule on F(s)=α'(2s), simplifying if-branch then
-- applying intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le with explicit antiderivative.
-- entry_kind: Builder
theorem left_half_eval_wrap
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    (∫ s in (0:ℝ)..((1:ℝ)/2),
      (if s ≤ (1:ℝ)/2
        then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
      = α' 1 - α' 0 := by
  -- Simplify: on [0, 1/2] we have s ≤ 1/2 always
  have h_simp : ∀ s ∈ Set.uIcc (0:ℝ) (1/2),
      (if s ≤ (1:ℝ)/2 then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
       else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) =
      2 * derivWithin α' (Set.Icc 0 1) (2*s) := by
    intro s hs
    rw [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1/2)] at hs
    exact if_pos hs.2
  rw [intervalIntegral.integral_congr h_simp]
  -- Apply FTC with antiderivative F(s) = α'(2*s)
  have hle : (0:ℝ) ≤ 1/2 := by norm_num
  -- Convert RHS to F(1/2) - F(0) where F(s) = α'(2*s)
  have hrhs : α' 1 - α' 0 = (fun s => α' (2 * s)) (1/2) - (fun s => α' (2 * s)) 0 := by
    norm_num
  rw [hrhs]
  refine intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le hle
    (f := fun s => α' (2 * s))
    (f' := fun s => 2 * derivWithin α' (Set.Icc 0 1) (2 * s)) ?_ ?_ ?_
  · -- ContinuousOn (fun s => α' (2 * s)) (Icc 0 (1/2))
    apply (hα'.continuousOn).comp (f := fun s : ℝ => 2 * s)
    · exact (continuous_const.mul continuous_id).continuousOn
    · intro s hs
      simp only [Set.mem_Icc] at hs ⊢
      exact ⟨by linarith [hs.1], by linarith [hs.2]⟩
  · -- HasDerivAt (fun s => α' (2*s)) (2 * derivWithin α' (Icc 0 1) (2*s)) s for s ∈ Ioo 0 (1/2)
    intro s hs
    have hs2 : 2 * s ∈ Set.Ioo (0:ℝ) 1 :=
      Set.mem_Ioo.mpr ⟨by linarith [hs.1], by linarith [hs.2]⟩
    have hs2mem : 2 * s ∈ Set.Icc (0:ℝ) 1 := Set.mem_Icc.mpr ⟨le_of_lt hs2.1, le_of_lt hs2.2⟩
    have hU : Set.Icc (0:ℝ) 1 ∈ nhds (2 * s) :=
      Icc_mem_nhds hs2.1 hs2.2
    have hda : DifferentiableAt ℝ α' (2 * s) :=
      (hα'.differentiableOn one_ne_zero (2 * s) hs2mem).differentiableAt hU
    have hderiv_eq : derivWithin α' (Set.Icc 0 1) (2 * s) = deriv α' (2 * s) :=
      hda.derivWithin (uniqueDiffWithinAt_of_mem_nhds hU)
    -- scomp: HasDerivAt (E-valued outer ∘ scalar inner) (h' • g₁') x
    have h2 : HasDerivAt (fun t : ℝ => 2 * t) (2:ℝ) s := by
      simpa using (hasDerivAt_id s).const_mul 2
    have hF_deriv := hda.hasDerivAt.scomp s h2
    -- hF_deriv : HasDerivAt (α' ∘ (2 * ·)) ((2:ℝ) • deriv α' (2*s)) s
    have hsmul : (2:ℝ) • deriv α' (2 * s) = (2:ℂ) * deriv α' (2 * s) := by
      simp [Algebra.smul_def]
    change HasDerivAt (fun s => α' (2 * s)) (2 * derivWithin α' (Set.Icc 0 1) (2 * s)) s
    rw [hderiv_eq, ← hsmul]
    exact hF_deriv
  · -- IntervalIntegrable via continuity of the integrand on [0, 1/2]
    apply ContinuousOn.intervalIntegrable_of_Icc hle
    apply ContinuousOn.mul continuousOn_const
    apply (hα'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl).comp
      (f := fun s : ℝ => 2 * s)
    · exact (continuous_const.mul continuous_id).continuousOn
    · intro s hs
      simp only [Set.mem_Icc] at hs ⊢
      exact ⟨by linarith [hs.1], by linarith [hs.2]⟩

end Problems.residue_thm