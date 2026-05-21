import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct one-shot: assemble C¹ regularity of the joint integrand
-- g(q) = f(H q.1 q.2) · fderivWithin H_joint q (0,1) on Icc×Icc, then take its
-- fderivWithin (continuous via ContDiffOn.continuousOn_fderivWithin on the
-- unique-diff product set), evaluate at the constant vector (1,0) via
-- ContinuousOn.clm_apply, and precompose with the continuous coordinate swap
-- p ↦ (p.2, p.1) (which is MapsTo Icc×Icc → Icc×Icc).
theorem s10363
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ContinuousOn
      (fun p : ℝ × ℝ =>
        fderivWithin ℝ
          (fun q : ℝ × ℝ =>
            f (H q.1 q.2) *
              fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
                (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) q ((0:ℝ), (1:ℝ)))
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (p.2, p.1) ((1:ℝ), (0:ℝ)))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)  := by
  -- 1. Show g(q) := f(H q.1 q.2) * fderivWithin H_joint q (0,1) is C¹ on Icc×Icc.
  -- 2. Hence fderivWithin g on Icc×Icc is continuous.
  -- 3. Apply at constant (1,0); precompose with continuous swap.
  have hfR : ContDiffOn ℝ 1 f V := by
    set_option backward.isDefEq.respectTransparency false in
    exact (hf.contDiffOn_of_completeSpace (n := 1)).restrict_scalars ℝ
  have hmaps : Set.MapsTo (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) V :=
    fun p hp => hHV p.1 hp.1 p.2 hp.2
  have h_fH : ContDiffOn ℝ 1 (fun p : ℝ × ℝ => f (H p.1 p.2))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    hfR.comp (hH.of_le (by norm_num)) hmaps
  have hUD : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    UniqueDiffOn.prod uniqueDiffOn_Icc_zero_one uniqueDiffOn_Icc_zero_one
  have h_dH : ContDiffOn ℝ 1
      (fun p : ℝ × ℝ =>
        fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    (hH.fderivWithin hUD (by norm_num)).clm_apply contDiffOn_const
  have h_g : ContDiffOn ℝ 1
      (fun q : ℝ × ℝ =>
        f (H q.1 q.2) *
          fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) q ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := h_fH.mul h_dH
  have h_fderiv_cont : ContinuousOn
      (fderivWithin ℝ
        (fun q : ℝ × ℝ =>
          f (H q.1 q.2) *
            fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) q ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    h_g.continuousOn_fderivWithin hUD le_rfl
  have h_apply : ContinuousOn
      (fun q : ℝ × ℝ =>
        fderivWithin ℝ
          (fun q : ℝ × ℝ =>
            f (H q.1 q.2) *
              fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
                (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) q ((0:ℝ), (1:ℝ)))
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) q ((1:ℝ), (0:ℝ)))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    h_fderiv_cont.clm_apply continuousOn_const
  have h_swap_cont : Continuous (fun p : ℝ × ℝ => (p.2, p.1)) :=
    continuous_snd.prodMk continuous_fst
  have h_swap_maps : Set.MapsTo (fun p : ℝ × ℝ => (p.2, p.1))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun p hp => ⟨hp.2, hp.1⟩
  exact h_apply.comp h_swap_cont.continuousOn h_swap_maps

end Problems.residue_thm
