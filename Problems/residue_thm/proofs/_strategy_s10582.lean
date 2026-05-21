import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_modulus_grid
import Problems.residue_thm.proofs.L_homotopy_uniform_thickening

namespace Problems.residue_thm

-- Lebesgue-grid construction for continuous H on the unit square into open U.
-- (1) `homotopy_uniform_thickening` (compact-image thickening): uniform δ>0 with
--     `ball (H τ t) δ ⊆ U` for every (τ,t) in the unit square.
-- (2) `homotopy_modulus_grid` (Heine-Cantor + Archimedean): given ε>0, pick N so
--     each N×N cell has diameter under H's modulus for ε.
-- Combine: take ε := δ. Then c i j := H (i/N) (j/N) and r i j := δ; the ball-in-U
-- condition uses (1) at grid points, and pointwise membership uses (2) with ε = δ.
theorem s10582
    {U : Set ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHmaps : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) :
    ∃ N : ℕ, 0 < N ∧ ∃ c : ℕ → ℕ → ℂ, ∃ r : ℕ → ℕ → ℝ,
      ∀ i j, i < N → j < N →
        0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
          (∀ τ ∈ Set.Icc ((i:ℝ)/N) (((i:ℝ)+1)/N),
            ∀ t ∈ Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N),
              H τ t ∈ Metric.ball (c i j) (r i j)) := by
  obtain ⟨δ, hδpos, hδball⟩ :=
    homotopy_uniform_thickening (U := U) (H := H) hU hHcont hHmaps
  obtain ⟨N, hNpos, hgrid⟩ :=
    homotopy_modulus_grid (H := H) hHcont δ hδpos
  refine ⟨N, hNpos, (fun i j => H ((i:ℝ)/N) ((j:ℝ)/N)), (fun _ _ => δ), ?_⟩
  intro i j hi hj
  have hNposR : (0 : ℝ) < (N : ℝ) := by exact_mod_cast hNpos
  have hiN : ((i:ℝ)/N) ∈ Set.Icc (0:ℝ) 1 := by
    refine ⟨div_nonneg (by exact_mod_cast Nat.zero_le i) hNposR.le, ?_⟩
    rw [div_le_one hNposR]; exact_mod_cast hi.le
  have hjN : ((j:ℝ)/N) ∈ Set.Icc (0:ℝ) 1 := by
    refine ⟨div_nonneg (by exact_mod_cast Nat.zero_le j) hNposR.le, ?_⟩
    rw [div_le_one hNposR]; exact_mod_cast hj.le
  refine ⟨hδpos, hδball ((i:ℝ)/N) hiN ((j:ℝ)/N) hjN, ?_⟩
  intro τ hτ t ht
  exact Metric.mem_ball.mpr (hgrid i j hi hj τ hτ t ht)

end Problems.residue_thm
