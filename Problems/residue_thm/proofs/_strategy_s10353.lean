import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct chain-rule proof: extract C¹ section `τ' ↦ H τ' t` from joint
-- `ContDiffOn ℝ 2 H` via `.comp` with the constant-t slice map, get its
-- `HasDerivWithinAt` on `Icc 0 1` at τ ∈ Ico 0 1, get `HasDerivAt` of `f`
-- at `H τ t ∈ V` from analyticity, then chain via `comp_hasDerivWithinAt`.
theorem s10353
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivWithinAt (fun τ' => f (H τ' t))
        (deriv f (H τ t) * derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ)
        (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ t ht
  have hmem_τ : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have hmem_t : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hHVmem : H τ t ∈ V := hHV τ hmem_τ t hmem_t
  have hHsec : ContDiffOn ℝ 1 (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) := by
    have hcomp : ContDiffOn ℝ 2 (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) := by
      have := hH.comp (contDiffOn_id.prodMk contDiffOn_const)
        (fun τ' hτ' => Set.mk_mem_prod hτ' hmem_t)
      simpa using this
    exact hcomp.of_le (by norm_num)
  have hHsec_hdw : HasDerivWithinAt (fun τ' => H τ' t)
      (derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ) (Set.Icc (0:ℝ) 1) τ :=
    ((hHsec.differentiableOn one_ne_zero) τ hmem_τ).hasDerivWithinAt
  have hf_hda : HasDerivAt f (deriv f (H τ t)) (H τ t) :=
    (hf.differentiableOn.differentiableAt (hV.mem_nhds hHVmem)).hasDerivAt
  exact hf_hda.comp_hasDerivWithinAt τ hHsec_hdw

end Problems.residue_thm
