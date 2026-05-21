import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_left_h_contdiff_wrap
import Problems.residue_thm.proofs.L_flat_left_h_eq_alpha_wrap

namespace Problems.residue_thm

-- integrand_dw_cont_on_left_half: ContinuousOn of Q(γ)·derivWithin γ (Icc 0 1) on Icc 0 (1/2).
-- γ is ContDiffOn ℝ 1 on Icc 0 1 (flat_left_h_contdiff_wrap), so derivWithin γ is continuous;
-- Q∘γ is continuous because γ t = α'(2t) ≠ a on Icc 0 (1/2) (flat_left_h_eq_alpha_wrap).
theorem integrand_dw_cont_on_left_half
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn
      (fun t : ℝ =>
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          derivWithin (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) (Set.Icc 0 1) t)
      (Set.Icc 0 (1/2)) := by
  set γ := fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
      (if s ≤ (1:ℝ)/2
        then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) with hγ_def
  have hγ_c1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1) :=
    flat_left_h_contdiff_wrap hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  have hγ_avoid : ∀ t ∈ Set.Icc (0:ℝ) (1/2), γ t ≠ a := by
    intro t ht
    have hγt := flat_left_h_eq_alpha_wrap hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match
        hα'_deriv hβ'_deriv t ht
    rw [show γ t = α' 0 + ∫ s in (0:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) from rfl, hγt]
    exact hα'_avoid (2*t) ⟨by linarith [ht.1], by linarith [ht.2]⟩
  have hγ_cont : ContinuousOn γ (Set.Icc 0 (1/2)) :=
    hγ_c1.continuousOn.mono (Set.Icc_subset_Icc_right (by norm_num))
  have hQγ_cont : ContinuousOn (fun t => Q (γ t)) (Set.Icc 0 (1/2)) :=
    hQ_an.continuousOn.comp hγ_cont (fun t ht => by
      simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
      exact hγ_avoid t ht)
  have hγ_dw_cont : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 (1/2)) :=
    (hγ_c1.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl).mono
      (Set.Icc_subset_Icc_right (by norm_num))
  exact hQγ_cont.mul hγ_dw_cont

end Problems.residue_thm
