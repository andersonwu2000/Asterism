import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_g_joint_diff_within_at_icc

namespace Problems.residue_thm

-- Chain rule for τ-section of the joint smooth `g(p) = f(H p.1 p.2) · ∂_t H @ p (0,1)`.
-- Sub-goal `g_joint_diff_within_at_icc` packages the joint `DifferentiableWithinAt` on
-- `Icc×Icc`; once obtained, `HasFDerivWithinAt.comp_hasDerivWithinAt` against the section
-- embedding `τ' ↦ (τ', t)` (derivative `(1,0)`) plus `uniqueDiffOn_Icc_zero_one` give the
-- pointwise `derivWithin = fderivWithin · (1,0)` identity.
theorem s10397
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
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) ((1:ℝ), (0:ℝ))  := by
  have h_diff := g_joint_diff_within_at_icc hV hf hH hHV hH0 hH1
  intro τ hτ t ht
  have hgfd := (h_diff τ hτ t ht).hasFDerivWithinAt
  have hsec : HasDerivWithinAt (fun τ' => (τ', t)) ((1:ℝ), (0:ℝ))
      (Set.Icc (0:ℝ) 1) τ :=
    (hasDerivWithinAt_id τ _).prodMk (hasDerivWithinAt_const τ _ t)
  have hmaps : Set.MapsTo (fun τ' => (τ', t))
      (Set.Icc (0:ℝ) 1) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun τ' hτ' => Set.mk_mem_prod hτ' ht
  have hchain := hgfd.comp_hasDerivWithinAt τ hsec hmaps
  exact hchain.derivWithin (uniqueDiffOn_Icc_zero_one τ hτ)

end Problems.residue_thm
