import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_apb_cover_step_wrapper

namespace Problems.residue_thm

-- Bottom-row (i = 0) of the homotopy grid is a 1D ball cover of γ:
-- γ s = H 0 s by hH0, and for each j < N the cell (0, j) places H 0 s ∈
-- ball (c 0 j) (r 0 j) ⊆ U on s ∈ [j/N, (j+1)/N].  Defer to a Builder
-- wrapper of the open sibling `analytic_path_int_zero_given_ball_cover`,
-- supplying the bottom-row cover (t k := k/N, c k := c 0 k, r k := r 0 k).
-- The grid's upper rows (homotopy connecting γ to the constant loop) are
-- not needed: row 0 alone provides the cover, since `analytic_path_int_zero_given_ball_cover`
-- already does the per-ball primitive + telescoping over the closed loop.
theorem s10583
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
  have hNR : (0 : ℝ) < (N : ℝ) := by exact_mod_cast hNpos
  have hNne : (N : ℝ) ≠ 0 := ne_of_gt hNR
  have h_apb_cover_step_wrapper :=
    apb_cover_step_wrapper hU hg hγ hmaps hclosed
      (n := N) (t := fun k => (k : ℝ) / N)
      (c := fun k => c 0 k) (r := fun k => r 0 k)
      (by show ((0 : ℕ) : ℝ) / N = 0; simp)
      (by show ((N : ℕ) : ℝ) / N = 1; field_simp)
      (fun k _ => by
        show (k : ℝ) / N ≤ ((k + 1 : ℕ) : ℝ) / N
        push_cast
        exact div_le_div_of_nonneg_right (by linarith) (le_of_lt hNR))
      (fun k hk => (hgrid 0 k hNpos hk).1)
      (fun k hk => (hgrid 0 k hNpos hk).2.1)
      (fun k hk s hs => by
        dsimp only at hs
        push_cast at hs
        have h_cell := (hgrid 0 k hNpos hk).2.2
        have hτ0 : (0 : ℝ) ∈ Set.Icc (((0 : ℕ) : ℝ) / N) ((((0 : ℕ) : ℝ) + 1) / N) := by
          refine ⟨?_, ?_⟩
          · simp
          · simp
        have h_in := h_cell 0 hτ0 s hs
        have hs_unit : s ∈ Set.Icc (0 : ℝ) 1 := by
          refine ⟨?_, ?_⟩
          · have h1 : (0 : ℝ) ≤ (k : ℝ) / N :=
              div_nonneg (by exact_mod_cast Nat.zero_le k) (le_of_lt hNR)
            exact le_trans h1 hs.1
          · refine le_trans hs.2 ?_
            rw [div_le_one hNR]
            exact_mod_cast hk
        show γ s ∈ Metric.ball (c 0 k) (r 0 k)
        rw [(hH0 s hs_unit).symm]
        exact h_in)
  exact h_apb_cover_step_wrapper

end Problems.residue_thm

