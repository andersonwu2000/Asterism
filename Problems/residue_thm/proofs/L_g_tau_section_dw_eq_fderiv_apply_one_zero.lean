import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- g_tau_section_dw_eq_fderiv_apply_one_zero: τ-section derivWithin of g equals
-- fderivWithin g in the (1,0) direction — section chain rule via ContDiffOn.mul + comp
-- entry_kind: Builder
theorem g_tau_section_dw_eq_fderiv_apply_one_zero
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin
          (fun τ' => f (H τ' t) *
            fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) ((0:ℝ), (1:ℝ)))
          (Set.Icc (0:ℝ) 1) τ =
        fderivWithin ℝ
          (fun q : ℝ × ℝ =>
            f (H q.1 q.2) *
              fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
                (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) q ((0:ℝ), (1:ℝ)))
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) ((1:ℝ), (0:ℝ)) := by
  intro τ hτ t ht
  set F := fun p : ℝ × ℝ => H p.1 p.2
  set S := Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1
  set g := fun q : ℝ × ℝ =>
    f (H q.1 q.2) * fderivWithin ℝ F S q ((0:ℝ), (1:ℝ))
  have huniq : UniqueDiffOn ℝ S :=
    UniqueDiffOn.prod uniqueDiffOn_Icc_zero_one uniqueDiffOn_Icc_zero_one
  have hg_C1 : ContDiffOn ℝ 1 g S := by
    apply ContDiffOn.mul
    · set_option backward.isDefEq.respectTransparency false in
      exact (hf.contDiffOn_of_completeSpace (n := 1) |>.restrict_scalars ℝ).comp
          (hH.of_le (by norm_num))
          (fun p hp => hHV p.1 (Set.mem_prod.mp hp).1 p.2 (Set.mem_prod.mp hp).2)
    · exact (hH.fderivWithin huniq (by norm_num)).clm_apply contDiffOn_const
  have hg_diff : DifferentiableWithinAt ℝ g S (τ, t) :=
    hg_C1.differentiableOn (by norm_num) (τ, t) (Set.mk_mem_prod hτ ht)
  have hgfd : HasFDerivWithinAt g (fderivWithin ℝ g S (τ, t)) S (τ, t) :=
    hg_diff.hasFDerivWithinAt
  have hsec : HasDerivWithinAt (fun τ' => (τ', t)) ((1:ℝ), (0:ℝ))
      (Set.Icc (0:ℝ) 1) τ :=
    (hasDerivWithinAt_id τ _).prodMk (hasDerivWithinAt_const τ _ t)
  have hmaps : Set.MapsTo (fun τ' => (τ', t)) (Set.Icc (0:ℝ) 1) S :=
    fun τ' hτ' => Set.mk_mem_prod hτ' ht
  have hcomp : HasDerivWithinAt (fun τ' => g (τ', t))
      (fderivWithin ℝ g S (τ, t) ((1:ℝ), (0:ℝ)))
      (Set.Icc (0:ℝ) 1) τ := by
    have h := hgfd.comp_hasDerivWithinAt τ hsec hmaps
    simp only [] at h
    exact h
  exact hcomp.derivWithin (uniqueDiffOn_Icc_zero_one τ hτ)

end Problems.residue_thm
