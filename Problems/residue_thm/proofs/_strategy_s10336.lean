import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_deriv_h_diff_in_tau
import Problems.residue_thm.proofs.L_f_compose_h_diff_in_tau

namespace Problems.residue_thm

-- Split the τ-derivative of the integrand at fixed t into chain-rule and
-- partial-derivative components, combined via the product rule. Both
-- sub-goals use t ∈ Ioo 0 1 to dodge `deriv (H τ) t` endpoint-junk.
theorem s10336
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ᵐ t ∂MeasureTheory.volume, t ∈ Set.uIoc (0:ℝ) 1 →
      ∀ x ∈ Set.Ioo (0:ℝ) 1,
        HasDerivAt (fun τ'' => f (H τ'' t) * deriv (H τ'') t)
          (deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) x) x  := by
  have hA := f_compose_h_diff_in_tau hV hf hH hHV hH0 hH1
  have hB := deriv_h_diff_in_tau hV hf hH hHV hH0 hH1
  have hae_ne : ∀ᵐ (t : ℝ) ∂MeasureTheory.volume, t ≠ 1 := by
    rw [MeasureTheory.ae_iff]
    simp
  filter_upwards [hae_ne] with t ht_ne hmem x hx
  have ht_ioc : t ∈ Set.Ioc (0:ℝ) 1 := by
    rwa [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)] at hmem
  have ht_ioo : t ∈ Set.Ioo (0:ℝ) 1 := ⟨ht_ioc.1, lt_of_le_of_ne ht_ioc.2 ht_ne⟩
  exact ((hA t ht_ioo x hx).mul (hB t ht_ioo x hx)).hasDerivAt

end Problems.residue_thm
