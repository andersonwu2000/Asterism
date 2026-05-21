import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_gamma_segment_int_eq_chord_int
import Problems.residue_thm.proofs.L_path_integral_split_subintervals

namespace Problems.residue_thm

-- Split the γ-path integral across N adjacent subintervals [j/N, (j+1)/N], then
-- equate each γ-segment integral with the chord integral via the row-0 ball-cover
-- primitive (γ-segment and chord both lie in ball (c 0 j) (r 0 j) ⊆ U, where g is
-- analytic and hence has a primitive on the ball).
-- (1) path_integral_split_subintervals — Builder: ∫₀¹ f = Σⱼ ∫_{j/N}^{(j+1)/N} f
--     via Finset.sum_integral_adjacent_intervals; integrand continuous on Icc 0 1.
-- (2) gamma_segment_int_eq_chord_int — Backward: per j, both segment and chord
--     integrals equal F(γ((j+1)/N)) - F(γ(j/N)) for the row-0 ball primitive F
--     (cite analytic_segment_primitive_diff via L_ auto-import; ball-convexity
--     places the chord inside ball (c 0 j) (r 0 j)).
-- Combinator: rewrite via hsplit, then Finset.sum_congr rfl hseg.
theorem s10617
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
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) =
      ∑ j ∈ Finset.range N,
        (∫ s in (0:ℝ)..1,
          g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
            * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N)))  := by
  have hsplit := path_integral_split_subintervals hU hg hγ hmaps N hNpos
  have hseg : ∀ j ∈ Finset.range N,
      (∫ t in ((j:ℝ)/N)..(((j:ℝ)+1)/N), g (γ t) * deriv γ t) =
        (∫ s in (0:ℝ)..1,
          g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
            * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N))) := by
    intro j hj
    exact gamma_segment_int_eq_chord_int hU hg hγ hmaps hHcont hH0 hHmaps
      N hNpos c r hgrid j hj
  rw [hsplit]
  exact Finset.sum_congr rfl hseg

end Problems.residue_thm
