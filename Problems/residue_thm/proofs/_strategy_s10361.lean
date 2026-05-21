import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderiv_apply_diff_within_at_prod

namespace Problems.residue_thm

-- Chain rule via the slice map `τ' ↦ (τ', t)`: pre-compose with the joint
-- DifferentiableWithinAt of `p ↦ fderivWithin ℝ G (Icc×Icc) p (0,1)` at the
-- prod point `(τ, t)` (sub-goal `fderiv_apply_diff_within_at_prod`, available
-- from the proved sibling `fderivwithin_joint_contdiff_one`'s `ContDiffOn ℝ 1`),
-- with the slice `(τ' ↦ (τ', t))` being differentiable and `MapsTo`-mapping
-- `Icc 0 1` into `Icc×Icc` thanks to `t ∈ Ioo ⊂ Icc`.
theorem s10361
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      DifferentiableWithinAt ℝ
        (fun τ' => fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) (0, 1))
        (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ t ht
  have hψ_pt :=
    fderiv_apply_diff_within_at_prod hV hf hH hHV hH0 hH1 τ hτ t ht
  have hslice : DifferentiableWithinAt ℝ (fun τ' : ℝ => (τ', t))
      (Set.Icc (0:ℝ) 1) τ :=
    ((differentiableAt_id (x := τ)).prodMk (differentiableAt_const t)).differentiableWithinAt
  have hmaps : Set.MapsTo (fun τ' : ℝ => (τ', t)) (Set.Icc (0:ℝ) 1)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := fun τ' hτ' =>
    Set.mk_mem_prod hτ' (Set.Ioo_subset_Icc_self ht)
  exact hψ_pt.comp τ hslice hmaps

end Problems.residue_thm
