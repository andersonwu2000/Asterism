import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_boundary_partials_vanish
import Problems.residue_thm.proofs.L_integral_tau_partial_eq_boundary_2

namespace Problems.residue_thm

-- Strategy: rewrite `deriv` as `derivWithin (Icc 0 1)` under the integral (Icc 0 1 ∈ 𝓝 τ for
-- τ ∈ Ioo), reduce via sibling `integral_tau_partial_eq_boundary_2` to the boundary difference
-- `f(H τ 1)·∂τ H(·,1) − f(H τ 0)·∂τ H(·,0)`, and conclude 0 via `boundary_partials_vanish`
-- (hH0/hH1 force `τ' ↦ H τ' 0` and `τ' ↦ H τ' 1` constant on Icc, so derivWithin vanishes).
theorem s10333
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ioo (0:ℝ) 1,
      (∫ t in (0:ℝ)..1, deriv (fun τ' => f (H τ' t) * deriv (H τ') t) τ) = 0  := by
  intro τ hτ
  have h_within :
      (∫ t in (0:ℝ)..1, deriv (fun τ' => f (H τ' t) * deriv (H τ') t) τ)
        = ∫ t in (0:ℝ)..1,
            derivWithin (fun τ' => f (H τ' t) * deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ := by
    refine intervalIntegral.integral_congr ?_
    intro t _
    exact (derivWithin_of_mem_nhds (Icc_mem_nhds hτ.1 hτ.2)).symm
  have h_boundary :=
    integral_tau_partial_eq_boundary_2 hV hf hH hHV hH0 hH1 τ (Set.Ioo_subset_Ico_self hτ)
  have h_zero :=
    boundary_partials_vanish hV hf hH hHV hH0 hH1 τ hτ
  rw [h_within, h_boundary, h_zero]

end Problems.residue_thm
