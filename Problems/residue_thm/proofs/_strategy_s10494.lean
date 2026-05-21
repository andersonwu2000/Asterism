import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_loop_piecewise_interp_through_balls

namespace Problems.residue_thm

-- Abstract the construction away from γ: reduce to a piecewise-C² interpolation
-- through an arbitrary point sequence (p i) lying in the prescribed balls.
-- Combine: instantiate p := γ ∘ t, verify each ball-membership from hgammacov, then close.
theorem s10494
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    (n : ℕ) (t : ℕ → ℝ) (centers : ℕ → ℂ) (radii : ℕ → ℝ)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i+1))
    (hrpos : ∀ i, i < n → 0 < radii i)
    (hballsubU : ∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U)
    (hgammacov : ∀ i, i < n →
      Set.MapsTo γ (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = γ 0 ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i ≤ n → η (t i) = γ (t i))  := by
  have hp_in_ball : ∀ i, i < n → γ (t i) ∈ Metric.ball (centers i) (radii i) := by
    intro i hi
    exact hgammacov i hi (Set.left_mem_Icc.mpr (htmono i hi))
  have hp_next_in_ball : ∀ i, i < n → γ (t (i+1)) ∈ Metric.ball (centers i) (radii i) := by
    intro i hi
    exact hgammacov i hi (Set.right_mem_Icc.mpr (htmono i hi))
  have hp_loop : γ (t n) = γ (t 0) := by
    rw [ht0, htn]; exact hclosed.symm
  have h_sub : ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = γ (t 0) ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i ≤ n → η (t i) = γ (t i)) :=
    c2_loop_piecewise_interp_through_balls
      (U := U) (n := n) (t := t) (p := fun i => γ (t i))
      (centers := centers) (radii := radii)
      hU ht0 htn htmono hrpos hballsubU hp_in_ball hp_next_in_ball hp_loop
  obtain ⟨η, hη_C2, hη_maps, hη_loop, hη0, hη_piece, hη_match⟩ := h_sub
  refine ⟨η, hη_C2, hη_maps, hη_loop, ?_, hη_piece, hη_match⟩
  rw [hη0, ht0]

end Problems.residue_thm
