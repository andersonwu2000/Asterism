import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_row_polygon_consec_eq
import Problems.residue_thm.proofs.L_row_polygon_telescope

namespace Problems.residue_thm

-- Decompose row-polygon homotopy invariance (τ=0 vs τ=1) into
-- (A) a single-step row equality `row_polygon_consec_eq` covering one strip τ ∈ [i/N, (i+1)/N]
-- (Cauchy on each cell ball plus telescoping over j), and (B) `row_polygon_telescope` which
-- iterates the step from i=0 to i=N to bridge τ=0 with τ=N/N=1.

theorem s10630
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
        g ((1 - (s:ℂ)) * H 0 ((j : ℝ) / N) + (s:ℂ) * H 0 (((j : ℝ) + 1) / N))
          * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N)))
    =
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * H 1 ((j : ℝ) / N) + (s:ℂ) * H 1 (((j : ℝ) + 1) / N))
          * (H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N)))  := by
  have h_step :=
    row_polygon_consec_eq (γ := γ) hU hg hHcont hHleft hHright hHmaps N hNpos c r hgrid
  exact row_polygon_telescope N hNpos h_step

end Problems.residue_thm
