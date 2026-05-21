import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderiv_e1_section_has_deriv_in_t
import Problems.residue_thm.proofs.L_partial_tau_eq_fderiv_apply_2

namespace Problems.residue_thm

-- Schwarz mixed-partial via fderivWithin reformulation. Two sub-goals:
-- (1) `partial_tau_eq_fderiv_apply_2` — the scalar derivWithin partial in τ equals
--     the (1,0)-direction of the joint fderivWithin on the product Icc × Icc.
-- (2) `fderiv_e1_section_has_deriv_in_t` — the fderivWithin (1,0)-section, viewed
--     as a function of t', has the swapped mixed partial as its t-derivative.
-- Transport (2) along the pointwise eq from (1) via `congr_of_eventuallyEq`,
-- using `Icc 0 1 ∈ 𝓝 t` (from `t ∈ Ioo 0 1`) for the neighborhood.
theorem s10346
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt
        (fun t' => derivWithin (fun τ' => H τ' t') (Set.Icc (0:ℝ) 1) τ)
        (derivWithin (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ) t  := by
  intro τ hτ t ht
  have h_partial_eq := partial_tau_eq_fderiv_apply_2 hV hf hH hHV hH0 hH1
  have h_fderiv_section :=
    fderiv_e1_section_has_deriv_in_t hV hf hH hHV hH0 hH1 τ hτ t ht
  exact h_fderiv_section.congr_of_eventuallyEq
    (Filter.eventually_of_mem (Icc_mem_nhds ht.1 ht.2)
      (fun t' ht' => h_partial_eq τ hτ t' ht'))

end Problems.residue_thm
