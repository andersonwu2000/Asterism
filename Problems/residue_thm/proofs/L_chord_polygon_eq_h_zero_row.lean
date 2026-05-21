import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- chord_polygon_eq_h_zero_row: rewrite γ → H 0 in chord-polygon sum via hH0 pointwise equality
-- entry_kind: Builder
theorem chord_polygon_eq_h_zero_row
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
          * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N)))
    =
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * H 0 ((j : ℝ) / N) + (s:ℂ) * H 0 (((j : ℝ) + 1) / N))
          * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N))) := by
    apply Finset.sum_congr rfl
    intro j hj
    have hj_lt : j < N := Finset.mem_range.mp hj
    have hjN : (0 : ℝ) < N := Nat.cast_pos.mpr hNpos
    have hj1 : (j : ℝ) / N ∈ Set.Icc (0:ℝ) 1 := by
      refine ⟨by positivity, (div_le_one hjN).mpr ?_⟩
      exact_mod_cast Nat.le_of_lt hj_lt
    have hj2 : ((j : ℝ) + 1) / N ∈ Set.Icc (0:ℝ) 1 := by
      refine ⟨by positivity, (div_le_one hjN).mpr ?_⟩
      exact_mod_cast hj_lt
    rw [hH0 _ hj1, hH0 _ hj2]




end Problems.residue_thm
