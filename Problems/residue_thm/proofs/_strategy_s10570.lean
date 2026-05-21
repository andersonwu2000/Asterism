import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_lebesgue_grid
import Problems.residue_thm.proofs.L_path_int_zero_given_homotopy_grid

namespace Problems.residue_thm

-- Discretize the continuous null-homotopy via a Lebesgue grid:
-- (1) `homotopy_lebesgue_grid` extracts N and per-cell balls in U covering H on each cell;
-- (2) `path_int_zero_given_homotopy_grid` runs the cell-boundary telescoping argument
--     (each cell-boundary PL loop lies in a ball, hence integrates to 0 by Cauchy on a ball;
--     the cell sum telescopes to the outer boundary, whose only nontrivial side is γ; the
--     constant sides give 0 via `hHleft`, `hHright`, `hH1`).
theorem s10570
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    (H : ℝ → ℝ → ℂ)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0:ℝ) 1, H 0 t = γ t)
    (hH1 : ∀ t ∈ Set.Icc (0:ℝ) 1, H 1 t = γ 0)
    (hHleft : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = γ 0)
    (hHright : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  obtain ⟨N, hNpos, c, r, hgrid⟩ :=
    homotopy_lebesgue_grid (U := U) (H := H) hU hHcont hHmaps
  exact path_int_zero_given_homotopy_grid (U := U) (g := g) (γ := γ) (H := H)
    hU hg hγ hmaps hclosed hHcont hH0 hH1 hHleft hHright hHmaps
    N hNpos c r hgrid

end Problems.residue_thm
