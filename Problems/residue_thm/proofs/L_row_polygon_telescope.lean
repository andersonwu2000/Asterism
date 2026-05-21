import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- row_polygon_telescope: Finset.range induction chains h_step N times to bridge τ=0 to τ=1.
-- entry_kind: Builder
theorem row_polygon_telescope
    {g : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (N : ℕ) (hNpos : 0 < N)
    (h_step : ∀ i : ℕ, i < N →
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
                - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))) :
    ∑ j ∈ Finset.range N,
      (∫ s in (0 : ℝ)..1,
        g ((1 - (s : ℂ)) * H 0 ((j : ℝ) / N) + (s : ℂ) * H 0 (((j : ℝ) + 1) / N))
          * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N)))
    =
    ∑ j ∈ Finset.range N,
      (∫ s in (0 : ℝ)..1,
        g ((1 - (s : ℂ)) * H 1 ((j : ℝ) / N) + (s : ℂ) * H 1 (((j : ℝ) + 1) / N))
          * (H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N))) := by
  -- Prove by induction: sum at row 0 = sum at row i/N for each i ≤ N, then specialize to i=N.
  suffices key : ∀ i : ℕ, i ≤ N →
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H 0 ((j : ℝ) / N) + (s : ℂ) * H 0 (((j : ℝ) + 1) / N))
            * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N))) =
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N))) by
    have hN : (N : ℝ) / N = 1 := div_self (Nat.cast_pos.mpr hNpos).ne'
    have hkey := key N le_rfl
    simp only [hN] at hkey
    exact hkey
  intro i hi
  induction i with
  | zero =>
    simp only [Nat.cast_zero, zero_div]
  | succ n ih =>
    have hn : n < N := Nat.lt_of_succ_le hi
    rw [ih (Nat.le_of_lt hn)]
    push_cast
    exact h_step n hn

end Problems.residue_thm
