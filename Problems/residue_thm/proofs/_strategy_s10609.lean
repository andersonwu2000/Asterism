import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_closed_glued_primitive_from_homotopy_grid
import Problems.residue_thm.proofs.L_integrand_interval_integrable_step_wrapper

namespace Problems.residue_thm

-- FTC-with-closed-primitive route, lifted from the ball-cover strategy s10495
-- but powered by the full 2D homotopy grid (the 1D-ball-cover variant was
-- disproved as `apb_cover_step_wrapper` — counterexample 1/z on the unit
-- circle). Sub-goal `closed_glued_primitive_from_homotopy_grid` (Backward)
-- builds a glued path-primitive F : ℝ → ℂ from per-cell local primitives on
-- the 2D grid, with telescoping constants across cells: the bottom row gives
-- HasDerivAt F (g(γ t)γ'(t)) on Ioo 0 1, the homotopy + constant sides
-- (hHleft, hHright, hH1) force F 0 = F 1. Sub-goal
-- `integrand_interval_integrable_step_wrapper` (Builder) wraps the proved
-- sibling `analytic_integrand_interval_integrable`. FTC then collapses the
-- integral to F 1 - F 0 = 0 via γ-closedness lifted to F-closedness.
theorem s10609
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0:ℝ) 1, H 0 t = γ t)
    (hH1 : ∀ t ∈ Set.Icc (0:ℝ) 1, H 1 t = γ 0)
    (hHleft : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = γ 0)
    (hHright : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i:ℝ)/N) (((i:ℝ)+1)/N),
          ∀ t ∈ Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  have h_int :=
    integrand_interval_integrable_step_wrapper hU hg hγ hmaps
  obtain ⟨F, hF_cont, hF_deriv, hF_closed⟩ :=
    closed_glued_primitive_from_homotopy_grid hU hg hγ hmaps hclosed
      hHcont hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  rw [intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le zero_le_one hF_cont hF_deriv h_int,
      ← hF_closed, sub_self]

end Problems.residue_thm
