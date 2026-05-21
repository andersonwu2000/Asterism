import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chord_polygon_eq_h_zero_row
import Problems.residue_thm.proofs.L_h_row_polygon_at_one_zero
import Problems.residue_thm.proofs.L_h_row_polygon_zero_to_one

namespace Problems.residue_thm

-- Decompose chord-polygon nullity into (A) substitution γ=H 0 on Icc 0 1 (hH0),
-- (B) row-polygon homotopy invariance from τ=0 to τ=1 via the grid cells, and
-- (C) degeneracy of the top-row polygon (H 1 ≡ γ 0). Sub-goal B carries the
-- meat (Cauchy on each ball-bounded cell plus telescoping rows) while A and C
-- are pure substitutions.
theorem s10616
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
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
          * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N))) = 0  := by
  have hA := chord_polygon_eq_h_zero_row hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  have hB := h_row_polygon_zero_to_one hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  have hC := h_row_polygon_at_one_zero hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  exact (hA.trans hB).trans hC

end Problems.residue_thm
