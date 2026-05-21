import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_tau_deriv_eq_dw_on_ioo_prod
import Problems.residue_thm.proofs.L_dw_integrand_section_cont_on_ioo

namespace Problems.residue_thm

-- Translate `deriv ... τ` at fixed τ ∈ Ioo 0 1 into the `derivWithin (Icc 0 1) τ`
-- formulation pointwise on t ∈ Ioo 0 1 (proved sibling `tau_deriv_eq_dw_on_ioo_prod`),
-- then close by `ContinuousOn.congr` against the section-continuity sub-goal in the
-- derivWithin form (`dw_integrand_section_cont_on_ioo`), which is structurally amenable
-- to slicing the joint `ContinuousOn (Icc×Icc)` of the integrand.
theorem s10354
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1)
    (τ : ℝ) (hτ : τ ∈ Set.Ioo (0:ℝ) 1) :
    ContinuousOn (fun t => deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) τ)
      (Set.Ioo (0:ℝ) 1)  := by
  have h_dw_cont :=
    dw_integrand_section_cont_on_ioo hV hf hH hHV hH0 hH1 τ hτ
  have h_eq :
      ∀ t ∈ Set.Ioo (0:ℝ) 1,
        deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) τ =
        derivWithin
          (fun τ'' => f (H τ'' t) * derivWithin (H τ'') (Set.Icc (0:ℝ) 1) t)
          (Set.Icc (0:ℝ) 1) τ := by
    intro t ht
    exact tau_deriv_eq_dw_on_ioo_prod hV hf hH hHV hH0 hH1 t ht τ hτ
  exact h_dw_cont.congr (fun t ht => h_eq t ht)

end Problems.residue_thm
