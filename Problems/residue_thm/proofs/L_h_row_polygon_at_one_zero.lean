import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- h_row_polygon_at_one_zero: top-row polygon integral is zero because hH1 forces all
-- chord differences to vanish (H 1 t = γ 0 for all t, so H 1 ((j+1)/N) - H 1 (j/N) = 0).
-- entry_kind: Builder
theorem h_row_polygon_at_one_zero
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
        g ((1 - (s:ℂ)) * H 1 ((j : ℝ) / N) + (s:ℂ) * H 1 (((j : ℝ) + 1) / N))
          * (H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N))) = 0 := by
  apply Finset.sum_eq_zero
  intro j hj
  have hjN : j < N := Finset.mem_range.mp hj
  have hj_mem : (j : ℝ) / N ∈ Set.Icc (0 : ℝ) 1 :=
    ⟨by positivity, by rw [div_le_one (by exact_mod_cast hNpos)]; exact_mod_cast hjN.le⟩
  have hj1_mem : ((j : ℝ) + 1) / N ∈ Set.Icc (0 : ℝ) 1 :=
    ⟨by positivity, by rw [div_le_one (by exact_mod_cast hNpos)]; exact_mod_cast hjN⟩
  have heq : H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N) = 0 := by
    rw [hH1 _ hj1_mem, hH1 _ hj_mem, sub_self]
  simp_rw [heq, mul_zero, intervalIntegral.integral_zero]

end Problems.residue_thm
