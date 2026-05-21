import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct chain-rule proof: extract a C¹ section `fun τ' => H τ' t` from the
-- joint `ContDiffOn ℝ 2 H` at interior `(x, t) ∈ Ioo × Ioo`, get its ℝ-
-- differentiability at `x`, get ℂ-differentiability of `f` at `H x t ∈ V`
-- from analyticity, then chain via `HasDerivAt.comp`.
theorem s10342
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ t ∈ Set.Ioo (0:ℝ) 1, ∀ x ∈ Set.Ioo (0:ℝ) 1,
      DifferentiableAt ℝ (fun τ'' => f (H τ'' t)) x  := by
  intro t ht x hx
  have hmem_x : x ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self hx
  have hmem_t : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hHVmem : H x t ∈ V := hHV x hmem_x t hmem_t
  have hHsec : ContDiffOn ℝ 1 (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) := by
    have hcomp : ContDiffOn ℝ 2 (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) := by
      have := hH.comp (contDiffOn_id.prodMk contDiffOn_const)
        (fun τ' hτ' => Set.mk_mem_prod hτ' hmem_t)
      simpa using this
    exact hcomp.of_le (by norm_num)
  have hHτDiff : DifferentiableAt ℝ (fun τ' => H τ' t) x :=
    (hHsec.differentiableOn one_ne_zero).differentiableAt
      (Icc_mem_nhds hx.1 hx.2)
  have hfDiff : DifferentiableAt ℂ f (H x t) :=
    hf.differentiableOn.differentiableAt (hV.mem_nhds hHVmem)
  exact (hfDiff.hasDerivAt.comp x hHτDiff.hasDerivAt).differentiableAt

end Problems.residue_thm
