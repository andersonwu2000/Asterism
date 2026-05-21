import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_partial_t_h_contdiffon_ioo

namespace Problems.residue_thm

-- Lift the τ-derivative `deriv (H τ) t` from a pointwise question at a single x
-- to ContDiffOn of the joint (τ, t) map on the open interior square.
-- Sub-goal `partial_t_h_contdiffon_ioo` packages the analytical content
-- (C¹ regularity of the t-partial as a function of (τ, t)); closing here is
-- a routine open-set restriction + composition with the C∞ slice τ ↦ (τ, t).
theorem s10341
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ t ∈ Set.Ioo (0:ℝ) 1, ∀ x ∈ Set.Ioo (0:ℝ) 1,
      DifferentiableAt ℝ (fun τ'' => deriv (H τ'') t) x  := by
  have hpartial : ContDiffOn ℝ 1 (fun p : ℝ × ℝ => deriv (H p.1) p.2)
      (Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1) :=
    partial_t_h_contdiffon_ioo hV hf hH hHV hH0 hH1
  intro t ht x hx
  have hmem : (x, t) ∈ Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1 := Set.mk_mem_prod hx ht
  have hopen : IsOpen (Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1) := isOpen_Ioo.prod isOpen_Ioo
  have h_diff_at : DifferentiableAt ℝ (fun p : ℝ × ℝ => deriv (H p.1) p.2) (x, t) :=
    (hpartial.contDiffAt (hopen.mem_nhds hmem)).differentiableAt (by norm_num)
  have hmap : DifferentiableAt ℝ (fun τ'' : ℝ => (τ'', t)) x :=
    (differentiableAt_id.prodMk (differentiableAt_const t))
  exact h_diff_at.comp x hmap

end Problems.residue_thm
