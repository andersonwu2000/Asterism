import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cell_quad_identity_on_ball

namespace Problems.residue_thm

-- Per-cell Cauchy quadrilateral identity: the four corners
-- BL = H(i/N,j/N), BR = H((i+1)/N,j/N), TR = H((i+1)/N,(j+1)/N), TL = H(i/N,(j+1)/N)
-- live in `Metric.ball (c i j) (r i j) ⊆ U` (via `hgrid`); since g is analytic on U
-- and hence DifferentiableOn ℂ on the ball, the closed quadrilateral integral
-- vanishes by `cell_quad_identity_on_ball`, yielding directly the desired
-- (vert-left − vert-right) = (bot − top) identity.
theorem s10644

    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    ∀ i j : ℕ, i < N → j < N →
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      -
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))
      =
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N))
            * (H (((i : ℝ) + 1) / N) ((j : ℝ) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      -
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H ((i : ℝ) / N) (((j : ℝ) + 1) / N))) := by
  intro i j hi hj
  obtain ⟨hr, hballU, hHcell⟩ := hgrid i j hi hj
  -- g is differentiable on the cell-ball (analytic on U ⊇ ball ⇒ differentiable on ball)
  have hgdiff : DifferentiableOn ℂ g (Metric.ball (c i j) (r i j)) :=
    (hg.mono hballU).differentiableOn
  -- four corners (BL, BR, TR, TL) live in the cell-ball
  have hN : (0 : ℝ) < (N : ℝ) := by exact_mod_cast hNpos
  have hinvN : (0 : ℝ) ≤ 1 / (N : ℝ) := by positivity
  have hi_le_i1 : (i : ℝ) / N ≤ ((i : ℝ) + 1) / N := by
    rw [div_le_div_iff_of_pos_right hN]; linarith
  have hj_le_j1 : (j : ℝ) / N ≤ ((j : ℝ) + 1) / N := by
    rw [div_le_div_iff_of_pos_right hN]; linarith



  have hmem_i_lo : ((i : ℝ) / N) ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) :=
    ⟨le_rfl, hi_le_i1⟩
  have hmem_i_hi : (((i : ℝ) + 1) / N) ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) :=
    ⟨hi_le_i1, le_rfl⟩
  have hmem_j_lo : ((j : ℝ) / N) ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N) :=
    ⟨le_rfl, hj_le_j1⟩
  have hmem_j_hi : (((j : ℝ) + 1) / N) ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N) :=
    ⟨hj_le_j1, le_rfl⟩
  have hBL : H ((i : ℝ) / N) ((j : ℝ) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_lo _ hmem_j_lo
  have hBR : H (((i : ℝ) + 1) / N) ((j : ℝ) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_hi _ hmem_j_lo
  have hTR : H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_hi _ hmem_j_hi
  have hTL : H ((i : ℝ) / N) (((j : ℝ) + 1) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_lo _ hmem_j_hi
  exact cell_quad_identity_on_ball hgdiff hBL hBR hTR hTL




end Problems.residue_thm
