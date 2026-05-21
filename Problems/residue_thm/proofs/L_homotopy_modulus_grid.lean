import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- homotopy_modulus_grid: Heine-Cantor uniform continuity on [0,1]² gives N-grid bound
-- Apply IsCompact.uniformContinuousOn_of_continuous, extract δ, pick N via exists_nat_one_div_lt.
theorem homotopy_modulus_grid
    {H : ℝ → ℝ → ℂ}
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (ε : ℝ) (hε : 0 < ε) :
    ∃ N : ℕ, 0 < N ∧
      ∀ i j, i < N → j < N →
        ∀ τ ∈ Set.Icc ((i:ℝ)/N) (((i:ℝ)+1)/N),
        ∀ t ∈ Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N),
          dist (H τ t) (H ((i:ℝ)/N) ((j:ℝ)/N)) < ε := by
  have hS : IsCompact (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    isCompact_Icc.prod isCompact_Icc
  have hunif := hS.uniformContinuousOn_of_continuous hHcont
  rw [Metric.uniformContinuousOn_iff] at hunif
  obtain ⟨δ, hδ, hunif⟩ := hunif ε hε
  obtain ⟨m, hm⟩ := exists_nat_one_div_lt hδ
  -- hm : 1 / (↑m + 1) < δ; use N = m + 1
  refine ⟨m + 1, Nat.succ_pos m, fun i j hi hj τ hτ t ht => ?_⟩
  have hN : (0 : ℝ) < (m : ℝ) + 1 := by positivity
  -- rewrite ↑(m+1) to ↑m+1 in hypotheses
  have hcastN : ((m + 1 : ℕ) : ℝ) = (m : ℝ) + 1 := by push_cast; ring
  rw [hcastN] at hτ ht
  -- Membership: τ ∈ [0,1]
  have hτ_ge0 : (0 : ℝ) ≤ τ := le_trans (by positivity) hτ.1
  have hτ_le1 : τ ≤ 1 := by
    have hend : ((i : ℝ) + 1) / ((m : ℝ) + 1) ≤ 1 := by
      rw [div_le_one hN]; norm_cast
    linarith [hτ.2]
  -- Membership: t ∈ [0,1]
  have ht_ge0 : (0 : ℝ) ≤ t := le_trans (by positivity) ht.1
  have ht_le1 : t ≤ 1 := by
    have hend : ((j : ℝ) + 1) / ((m : ℝ) + 1) ≤ 1 := by
      rw [div_le_one hN]; norm_cast
    linarith [ht.2]
  -- Grid point membership
  have hgi_ge0 : (0 : ℝ) ≤ (i : ℝ) / ((m : ℝ) + 1) := by positivity
  have hgi_le1 : (i : ℝ) / ((m : ℝ) + 1) ≤ 1 := by
    rw [div_le_one hN]; norm_cast; omega
  have hgj_ge0 : (0 : ℝ) ≤ (j : ℝ) / ((m : ℝ) + 1) := by positivity

  have hgj_le1 : (j : ℝ) / ((m : ℝ) + 1) ≤ 1 := by
    rw [div_le_one hN]; norm_cast; omega
  -- Set membership assertions
  have hτ_mem : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 :=
    ⟨⟨hτ_ge0, hτ_le1⟩, ht_ge0, ht_le1⟩
  have hpt_mem : ((i:ℝ)/((m:ℝ)+1), (j:ℝ)/((m:ℝ)+1)) ∈
      Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 :=
    ⟨⟨hgi_ge0, hgi_le1⟩, hgj_ge0, hgj_le1⟩
  -- Distance bound: both coordinates differ by at most 1/(m+1) < δ
  have hdist : dist (τ, t) ((i:ℝ)/((m:ℝ)+1), (j:ℝ)/((m:ℝ)+1)) < δ := by
    rw [Prod.dist_eq]
    apply max_lt
    · rw [Real.dist_eq]
      have heq : ((i:ℝ)+1)/((m:ℝ)+1) = (i:ℝ)/((m:ℝ)+1) + 1/((m:ℝ)+1) := by
        field_simp
      have hup : τ - (i:ℝ)/((m:ℝ)+1) ≤ 1/((m:ℝ)+1) := by linarith [hτ.2, heq]
      have hlo : -(1/((m:ℝ)+1)) ≤ τ - (i:ℝ)/((m:ℝ)+1) := by
        linarith [hτ.1, div_pos one_pos hN]
      exact lt_of_le_of_lt (abs_le.mpr ⟨hlo, hup⟩) hm
    · rw [Real.dist_eq]
      have heq : ((j:ℝ)+1)/((m:ℝ)+1) = (j:ℝ)/((m:ℝ)+1) + 1/((m:ℝ)+1) := by
        field_simp
      have hup : t - (j:ℝ)/((m:ℝ)+1) ≤ 1/((m:ℝ)+1) := by linarith [ht.2, heq]
      have hlo : -(1/((m:ℝ)+1)) ≤ t - (j:ℝ)/((m:ℝ)+1) := by
        linarith [ht.1, div_pos one_pos hN]
      exact lt_of_le_of_lt (abs_le.mpr ⟨hlo, hup⟩) hm
  -- Apply uniform continuity; unfold Function.uncurry
  rw [hcastN]
  have key := hunif (τ, t) hτ_mem ((i:ℝ)/((m:ℝ)+1), (j:ℝ)/((m:ℝ)+1)) hpt_mem hdist
  simp only [Function.uncurry] at key
  exact key

end Problems.residue_thm
