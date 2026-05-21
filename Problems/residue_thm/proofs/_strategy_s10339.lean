import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_derivwithin_section_product_chain_eq
import Problems.residue_thm.proofs.L_f_section_chain_rule
import Problems.residue_thm.proofs.L_partial_tau_has_deriv_in_t

namespace Problems.residue_thm

-- Decompose `dG/dt = X` at `(τ, t) ∈ Ico × Ioo` into:
-- (1) `f_section_chain_rule` — chain rule for `t' ↦ f(H τ t')` at interior `t`.
-- (2) `partial_tau_has_deriv_in_t` — Schwarz mixed-partial:
--     `t' ↦ ∂_{τ'} H(τ, t')` has `t`-derivative `∂_{τ'} ∂_t H(τ, t)`.
-- (3) `derivwithin_section_product_chain_eq` — derivWithin product+chain
--     rule equating the `HasDerivAt.mul` output to the parent's `derivWithin` form.
-- Combine (1) and (2) via `HasDerivAt.mul`, then rewrite the value with (3).
theorem s10339
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
        (fun t' => f (H τ t') * derivWithin (fun τ' => H τ' t') (Set.Icc (0:ℝ) 1) τ)
        (derivWithin (fun τ' => f (H τ' t) * deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ) t  := by
  intro τ hτ t ht
  have h_f : HasDerivAt (fun t' => f (H τ t'))
      (deriv f (H τ t) * deriv (H τ) t) t :=
    f_section_chain_rule hV hf hH hHV hH0 hH1 τ hτ t ht
  have h_partial : HasDerivAt (fun t' => derivWithin (fun τ' => H τ' t') (Set.Icc (0:ℝ) 1) τ)
      (derivWithin (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ) t :=
    partial_tau_has_deriv_in_t hV hf hH hHV hH0 hH1 τ hτ t ht
  have h_eq :
      deriv f (H τ t) * deriv (H τ) t * derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ
        + f (H τ t) * derivWithin (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ
      = derivWithin (fun τ' => f (H τ' t) * deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ :=
    derivwithin_section_product_chain_eq hV hf hH hHV hH0 hH1 τ hτ t ht
  exact h_eq ▸ h_f.mul h_partial

end Problems.residue_thm
