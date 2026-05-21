import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cell_primitives_choice
import Problems.residue_thm.proofs.L_closed_glued_f_from_grid_cells

namespace Problems.residue_thm

-- Decompose into (a) Builder choice of per-cell local primitives P : ℕ → ℕ → ℂ → ℂ
-- on each grid ball (HasDerivAt (P i j) (g z) z for z in ball (c i j) (r i j)),
-- (b) Backward gluing of F : ℝ → ℂ from those explicit primitives along the
-- bottom row (τ=0, where hH0 + hgrid give γ([j/N,(j+1)/N]) ⊆ ball(c 0 j)(r 0 j)),
-- with the 2D telescoping closure F 0 = F 1 driven by hHleft/hHright/hH1 over
-- the rows. Step (a) is mechanical (Classical.choose + primitive_exists_on_ball_of_diff_on);
-- step (b) is the substantive construction.
theorem s10622
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
    ∃ F : ℝ → ℂ,
      ContinuousOn F (Set.Icc (0:ℝ) 1) ∧
      (∀ s ∈ Set.Ioo (0:ℝ) 1, HasDerivAt F (g (γ s) * deriv γ s) s) ∧
      F 0 = F 1  := by
  have hball : ∀ i j, i < N → j < N → Metric.ball (c i j) (r i j) ⊆ U :=
    fun i j hi hj => (hgrid i j hi hj).2.1
  have h_cells := cell_primitives_choice hg N c r hball
  obtain ⟨P, hP⟩ := h_cells
  exact closed_glued_f_from_grid_cells hU hg hγ hmaps hclosed
    hHcont hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid P hP

end Problems.residue_thm
