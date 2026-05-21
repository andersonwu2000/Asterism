import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_path_integral_deriv_within_zero
import Problems.residue_thm.proofs.L_homotopy_path_integral_differentiable_on

namespace Problems.residue_thm

-- Reduce homotopy invariance to constancy of `J(τ) := ∫₀¹ f(H τ t)·∂ₜ(H τ) t dt`
-- on `Icc 0 1` via `constant_of_derivWithin_zero`. Sub-goal (a) is the
-- differentiation-under-the-integral analysis (parameter-dependent integral
-- with `C²` integrand). Sub-goal (b) carries the analytic core: the
-- τ-derivative equals `[f(H τ t)·∂_τH τ t]_{t=0}^{t=1}` by Clairaut +
-- Cauchy-Riemann, which vanishes by the endpoint-fixing hypotheses
-- `hH0`/`hH1`. Closer evaluates the constancy conclusion at `τ = 1`.
theorem s10327
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    (∫ t in (0:ℝ)..1, f (H 0 t) * deriv (H 0) t) =
      (∫ t in (0:ℝ)..1, f (H 1 t) * deriv (H 1) t)  := by
  have h_diff := homotopy_path_integral_differentiable_on hV hf hH hHV hH0 hH1
  have h_zero := homotopy_path_integral_deriv_within_zero hV hf hH hHV hH0 hH1
  have h_const := constant_of_derivWithin_zero h_diff h_zero
  exact (h_const 1 (Set.right_mem_Icc.mpr zero_le_one)).symm


end Problems.residue_thm
