import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cell_quad_chord_vert_diff

namespace Problems.residue_thm

-- Decompose row-strip homotopy invariance into per-cell Cauchy identities
-- on each ball B(c i j, r i j) and a telescoping sum over j.
-- (A) `cell_quad_chord_vert_diff`: on each cell (i,j), the chord-top minus
--     chord-bot equals V(i,j) − V(i,j+1) (Cauchy on the four corners of the
--     cell quadrilateral, all in Metric.ball (c i j) (r i j) ⊆ U).
-- Combinator: sum (A) over j ∈ range N. The RHS telescopes via
-- `Finset.sum_range_sub'` to V(i,0) − V(i,N). Both ends vanish: H τ 0 = γ 0
-- and H τ 1 = γ 0 force the integrand factor to be zero, and (N:ℝ)/N = 1
-- handles the upper boundary.
theorem s10639
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
    ∀ i : ℕ, i < N →
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      =
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))  := by
  intro i hi
  have h_cell :
      ∀ j : ℕ, j < N →
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
                  - H ((i : ℝ) / N) (((j : ℝ) + 1) / N))) := fun j hj =>
    cell_quad_chord_vert_diff hU hg hHcont hHleft hHright hHmaps N hNpos c r hgrid i j hi hj
  -- Define the vertical-chord integral at column k for the strip [i/N, (i+1)/N].
  set v : ℕ → ℂ := fun k =>
    ∫ s in (0 : ℝ)..1,
      g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((k : ℝ) / N)
          + (s : ℂ) * H (((i : ℝ) + 1) / N) ((k : ℝ) / N))
        * (H (((i : ℝ) + 1) / N) ((k : ℝ) / N) - H ((i : ℝ) / N) ((k : ℝ) / N))
    with hv
  -- Boundary: at column 0, both H τ 0 = γ 0, so the integrand factor vanishes.
  have h_v0 : v 0 = 0 := by
    have hiL : ((i : ℝ) / N) ∈ Set.Icc (0 : ℝ) 1 := by
      refine ⟨?_, ?_⟩
      · exact div_nonneg (Nat.cast_nonneg _) (Nat.cast_nonneg _)
      · rw [div_le_one (by exact_mod_cast hNpos)]
        exact_mod_cast Nat.le_of_lt hi
    have hiR : (((i : ℝ) + 1) / N) ∈ Set.Icc (0 : ℝ) 1 := by
      refine ⟨?_, ?_⟩
      · exact div_nonneg (by positivity) (Nat.cast_nonneg _)
      · rw [div_le_one (by exact_mod_cast hNpos)]
        have : (i : ℝ) + 1 ≤ N := by exact_mod_cast Nat.succ_le_of_lt hi
        exact this
    have hL : H ((i : ℝ) / N) 0 = γ 0 := hHleft _ hiL
    have hR : H (((i : ℝ) + 1) / N) 0 = γ 0 := hHleft _ hiR
    simp [v, hL, hR]
  -- Boundary: at column N, (N:ℝ)/N = 1 and H τ 1 = γ 0.
  have h_vN : v N = 0 := by
    have hN1 : (N : ℝ) / N = 1 := div_self (by exact_mod_cast hNpos.ne')
    have hiL : ((i : ℝ) / N) ∈ Set.Icc (0 : ℝ) 1 := by
      refine ⟨?_, ?_⟩
      · exact div_nonneg (Nat.cast_nonneg _) (Nat.cast_nonneg _)
      · rw [div_le_one (by exact_mod_cast hNpos)]
        exact_mod_cast Nat.le_of_lt hi
    have hiR : (((i : ℝ) + 1) / N) ∈ Set.Icc (0 : ℝ) 1 := by
      refine ⟨?_, ?_⟩
      · exact div_nonneg (by positivity) (Nat.cast_nonneg _)
      · rw [div_le_one (by exact_mod_cast hNpos)]
        have : (i : ℝ) + 1 ≤ N := by exact_mod_cast Nat.succ_le_of_lt hi
        exact this
    have hL : H ((i : ℝ) / N) 1 = γ 0 := hHright _ hiL
    have hR : H (((i : ℝ) + 1) / N) 1 = γ 0 := hHright _ hiR
    simp [v, hN1, hL, hR]
  -- Reframe h_cell's RHS as v j - v (j+1).
  have h_cell_v : ∀ j : ℕ, j < N →
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
      = v j - v (j + 1) := by
    intro j hj
    have := h_cell j hj
    simp only [v]
    push_cast
    convert this using 2
  -- Sum the cell identity over j ∈ range N; telescope to v 0 - v N = 0.
  have h_telescope :
      ∑ j ∈ Finset.range N, (v j - v (j + 1)) = 0 := by
    rw [Finset.sum_range_sub']
    rw [h_v0, h_vN]
    ring
  have h_diff_sum :
      ∑ j ∈ Finset.range N,
        ((∫ s in (0 : ℝ)..1,
            g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
                + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
              * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
        -
        (∫ s in (0 : ℝ)..1,
            g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
                + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
              * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                  - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))) = 0 := by
    rw [Finset.sum_congr rfl (fun j hj => h_cell_v j (Finset.mem_range.mp hj))]
    exact h_telescope
  -- ∑(top - bot) = 0 ⇒ ∑ top - ∑ bot = 0 ⇒ ∑ top = ∑ bot.
  have h_split :
      (∑ j ∈ Finset.range N,
          (∫ s in (0 : ℝ)..1,
            g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
                + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
              * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N))))
      -
      (∑ j ∈ Finset.range N,
          (∫ s in (0 : ℝ)..1,
            g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
                + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
              * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                  - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))) = 0 := by
    rw [← Finset.sum_sub_distrib]
    exact h_diff_sum
  exact sub_eq_zero.mp h_split

end Problems.residue_thm
