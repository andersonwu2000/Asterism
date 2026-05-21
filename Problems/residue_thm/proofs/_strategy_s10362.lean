import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_tau_dw_integrand_joint_continuous

namespace Problems.residue_thm

-- Slice the (already-declared open sibling) joint τ-derivWithin integrand
-- continuity on `Icc 0 1 ×ˢ Icc 0 1` along `t ↦ (t, τ)`; since `Ioo ⊆ Icc`,
-- the slice map is continuous on `Ioo 0 1` and lands in the product, so the
-- composition closes the goal directly via `ContinuousOn.comp`.
theorem s10362
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1)
    (τ : ℝ) (hτ : τ ∈ Set.Ioo (0:ℝ) 1) :
    ContinuousOn
      (fun t => derivWithin
        (fun τ'' => f (H τ'' t) * derivWithin (H τ'') (Set.Icc (0:ℝ) 1) t)
        (Set.Icc (0:ℝ) 1) τ)
      (Set.Ioo (0:ℝ) 1)  := by
  have h_joint := tau_dw_integrand_joint_continuous hV hf hH hHV hH0 hH1
  exact h_joint.comp
    (by fun_prop : ContinuousOn (fun t' : ℝ => (t', τ)) (Set.Ioo (0:ℝ) 1))
    (fun s hs => Set.mk_mem_prod (Set.Ioo_subset_Icc_self hs) (Set.Ioo_subset_Icc_self hτ))

end Problems.residue_thm
