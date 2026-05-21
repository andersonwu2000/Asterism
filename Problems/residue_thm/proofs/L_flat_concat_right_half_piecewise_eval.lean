import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem flat_concat_right_half_piecewise_eval
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      (∫ s in ((1:ℝ)/2:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = β' (2*t - 1) - β' 0 := by
  intro t ht
  -- Step 1: piecewise = else branch pointwise on [1/2, t]
  have h1 : ∫ s in ((1:ℝ)/2)..t,
      (if s ≤ (1:ℝ)/2 then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
       else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) =
    ∫ s in ((1:ℝ)/2:ℝ)..t, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1) := by
    apply intervalIntegral.integral_congr
    intro s hs
    simp only [Set.uIcc_of_le ht.1, Set.mem_Icc] at hs
    by_cases heq : s = 1/2
    · subst heq
      have hv1 : (2:ℝ) * (1/2:ℝ) = 1 := by norm_num
      simp only [le_refl, if_true, hv1, hα'_deriv, mul_zero, sub_self, hβ'_deriv]
    · have hs_gt : ¬ s ≤ 1/2 := not_le.mpr (lt_of_le_of_ne hs.1 (Ne.symm heq))
      simp only [hs_gt, if_false]
  rw [h1]
  -- Step 2: Pull out constant 2
  have h2 : ∫ s in ((1:ℝ)/2)..t, (2 : ℂ) * derivWithin β' (Set.Icc 0 1) (2*s - 1) =
      2 * ∫ s in ((1:ℝ)/2)..t, derivWithin β' (Set.Icc 0 1) (2*s - 1) :=
    intervalIntegral.integral_const_mul 2 _
  rw [h2]
  -- Step 3: Change of variables: ∫_{1/2}^t f(2s-1) = 2⁻¹ · ∫_0^{2t-1} f(u)
  have h3 : ∫ s in ((1:ℝ)/2)..t, derivWithin β' (Set.Icc 0 1) (2*s - 1) =
      (2:ℝ)⁻¹ • ∫ u in (0:ℝ)..(2*t - 1), derivWithin β' (Set.Icc 0 1) u := by
    have ha : ∫ s in ((1:ℝ)/2)..t, derivWithin β' (Set.Icc 0 1) (2*s - 1) =
        (2:ℝ)⁻¹ • ∫ u in ((2:ℝ) * (1/2))..(2*t), derivWithin β' (Set.Icc 0 1) (u - 1) :=
      intervalIntegral.integral_comp_mul_left
        (fun u => derivWithin β' (Set.Icc 0 1) (u - 1)) (two_ne_zero' ℝ)
    simp only [show (2:ℝ) * (1/2) = 1 from by norm_num] at ha
    rw [ha]; congr 1
    have hb : ∫ u in (1:ℝ)..(2*t), derivWithin β' (Set.Icc 0 1) (u - 1) =
        ∫ v in ((1:ℝ) - 1)..(2*t - 1), derivWithin β' (Set.Icc 0 1) v :=
      intervalIntegral.integral_comp_sub_right (derivWithin β' (Set.Icc 0 1)) 1
    simp only [show (1:ℝ) - 1 = 0 from by norm_num] at hb
    exact hb
  rw [h3]
  -- Step 4: FTC on [0, 2t-1] ⊆ [0, 1]
  have h_le : (0:ℝ) ≤ 2*t - 1 := by linarith [ht.1]
  have h_le1 : 2*t - 1 ≤ 1 := by linarith [ht.2]
  have h4 : ∫ u in (0:ℝ)..(2*t - 1), derivWithin β' (Set.Icc 0 1) u = β' (2*t - 1) - β' 0 := by
    have hF_cont : ContinuousOn β' (Set.Icc 0 (2*t - 1)) :=
      hβ'.continuousOn.mono (Set.Icc_subset_Icc_right h_le1)
    have hF_deriv : ∀ x ∈ Set.Ioo 0 (2*t - 1),
        HasDerivAt β' (derivWithin β' (Set.Icc 0 1) x) x := by
      intro x hx
      have hx1 : x ∈ Set.Ioo 0 1 := Set.Ioo_subset_Ioo_right h_le1 hx
      have hmem : x ∈ Set.Icc 0 1 :=
        Set.mem_Icc.mpr ⟨le_of_lt hx1.1, le_of_lt hx1.2⟩
      have hU : Set.Icc 0 1 ∈ nhds x := Icc_mem_nhds hx1.1 hx1.2
      have hda : DifferentiableAt ℝ β' x :=
        (hβ'.differentiableOn one_ne_zero x hmem).differentiableAt hU
      rw [hda.derivWithin (uniqueDiffWithinAt_of_mem_nhds hU)]
      exact hda.hasDerivAt
    have hcont_deriv : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 (2*t - 1)) :=
      (hβ'.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl).mono
        (Set.Icc_subset_Icc_right h_le1)
    exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le h_le hF_cont hF_deriv
      (hcont_deriv.intervalIntegrable_of_Icc h_le)
  rw [h4]
  -- Step 5: 2 * (2⁻¹ • v) = v
  rw [Complex.real_smul]
  push_cast
  ring

end Problems.residue_thm
