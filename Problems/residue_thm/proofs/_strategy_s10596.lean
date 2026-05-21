import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chord_polygon_int_zero
import Problems.residue_thm.proofs.L_gamma_int_eq_chord_polygon

namespace Problems.residue_thm

-- Reduce the path integral to a chord polygon, then telescope via the homotopy grid.
-- (1) `gamma_int_eq_chord_polygon` — each γ-segment over [j/N, (j+1)/N] lies in
--     ball (c 0 j) (r 0 j) ⊆ U (bottom row of the grid); on a ball g has a primitive,
--     so the segment integral equals the chord integral with endpoints γ(j/N), γ((j+1)/N).
--     Summing over j rewrites ∫₀¹ g(γ)·γ' as the chord-polygon integral.
-- (2) `chord_polygon_int_zero` — the chord polygon over (γ(j/N))_{j=0..N} is null-homotopic
--     via the grid: define row-polygons R_i with vertices V(i,j) := H(i/N, j/N); each cell
--     (i,j) loop integrates to 0 by Cauchy on ball (c i j) (r i j); the four-edge cancellation
--     gives R_i = R_{i+1} (using hHleft, hHright as zero left/right τ-chords); induction on i
--     from i=0 (= chord polygon of γ via hH0) up to i=N (constant, zero via hH1).
theorem s10596
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
  have h_eq := gamma_int_eq_chord_polygon hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  have h_zero := chord_polygon_int_zero hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  exact h_eq.trans h_zero

end Problems.residue_thm
