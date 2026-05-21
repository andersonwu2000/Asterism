import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_deriv_section_eq_fderivwithin_apply
import Problems.residue_thm.proofs.L_fderivwithin_section_diff_within_tau

namespace Problems.residue_thm

-- Rewrite `deriv (H τ') t` pointwise to `fderivWithin G (Icc×Icc) (τ', t) (0,1)` on
-- τ' ∈ Icc 0 1 (sub-goal 1, chain rule via slice map + `Icc ∈ nhds t` for interior t),
-- then transfer DifferentiableWithinAt in τ from the fderivWithin form (sub-goal 2,
-- `ContDiffOn.fderivWithin` ↑ slice-map composition) via `DifferentiableWithinAt.congr`.
theorem s10352
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      DifferentiableWithinAt ℝ (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ t ht
  have h1 := deriv_section_eq_fderivwithin_apply hV hf hH hHV hH0 hH1
  have h2 := fderivwithin_section_diff_within_tau hV hf hH hHV hH0 hH1 τ hτ t ht
  exact h2.congr
    (fun τ' hτ' => h1 τ' hτ' t ht)
    (h1 τ (Set.Ico_subset_Icc_self hτ) t ht)

end Problems.residue_thm
