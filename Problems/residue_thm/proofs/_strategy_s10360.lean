import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_derivwithin_eq_fderivwithin_section_t

namespace Problems.residue_thm

-- Two-step transfer: (1) `deriv (H τ') t = derivWithin (H τ') (Icc 0 1) t` via
-- `derivWithin_of_mem_nhds` since `Icc 0 1 ∈ 𝓝 t` for interior `t ∈ Ioo 0 1`;
-- (2) the slice chain rule sub-goal `derivwithin_eq_fderivwithin_section_t`
-- handles `derivWithin (H τ') (Icc 0 1) t = fderivWithin G (Icc×Icc) (τ',t) (0,1)`
-- using `HasFDerivWithinAt.comp_hasDerivWithinAt_of_eq` on the slice `t' ↦ (τ',t')`.
theorem s10360
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ' ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      deriv (H τ') t =
        fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) (0, 1)  := by
  intro τ' hτ' t ht
  have h_chain := derivwithin_eq_fderivwithin_section_t
    hV hf hH hHV hH0 hH1 τ' hτ' t ht
  have h_eq : deriv (H τ') t = derivWithin (H τ') (Set.Icc (0:ℝ) 1) t :=
    (derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)).symm
  exact h_eq.trans h_chain

end Problems.residue_thm
