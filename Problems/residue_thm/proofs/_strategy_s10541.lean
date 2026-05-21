import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_piecewise_lerp_in_segments
import Problems.residue_thm.proofs.L_unit_icc_covered_by_partition

namespace Problems.residue_thm

-- Decompose: build η via abstract piecewise lerp into per-step segments,
-- then convert segment-membership to ball/U membership via ball convexity.
-- Sub-goals:
--   (1) `c2_piecewise_lerp_in_segments` — C² interp core, segment-targeted.
--   (2) `unit_icc_covered_by_partition` — every τ ∈ Icc 0 1 lies in some Icc (t i) (t (i+1)).
theorem s10541
    {U : Set ℂ} {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ) (centers : ℕ → ℂ) (radii : ℕ → ℝ)
    (hU : IsOpen U)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i+1))
    (hrpos : ∀ i, i < n → 0 < radii i)
    (hballsubU : ∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U)
    (hp_in_ball : ∀ i, i < n → p i ∈ Metric.ball (centers i) (radii i))
    (hp_next_in_ball : ∀ i, i < n → p (i+1) ∈ Metric.ball (centers i) (radii i))
    (hp_loop : p n = p 0)
    (hp_collapse : ∀ i, i < n → t i = t (i+1) → p i = p (i+1)) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = p 0 ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i ≤ n → η (t i) = p i)  := by
  obtain ⟨η, hη_C2, hη_interp, hη_seg⟩ :=
    c2_piecewise_lerp_in_segments t p ht0 htn htmono hp_collapse
  have hseg_ball : ∀ i, i < n →
      segment ℝ (p i) (p (i + 1)) ⊆ Metric.ball (centers i) (radii i) := by
    intro i hin
    exact (convex_ball (centers i) (radii i)).segment_subset
      (hp_in_ball i hin) (hp_next_in_ball i hin)
  refine ⟨η, hη_C2, ?_, ?_, ?_, ?_, hη_interp⟩
  · intro τ hτ
    obtain ⟨i, hin, hτi⟩ := unit_icc_covered_by_partition t ht0 htn htmono hτ
    exact hballsubU i hin (hseg_ball i hin (hη_seg i hin hτi))
  · have h0 : η 0 = p 0 := by
      have := hη_interp 0 (Nat.zero_le n); rwa [ht0] at this
    have h1 : η 1 = p n := by
      have := hη_interp n le_rfl; rwa [htn] at this
    rw [h0, h1, hp_loop]
  · have := hη_interp 0 (Nat.zero_le n); rwa [ht0] at this
  · intro i hin τ hτ
    exact hseg_ball i hin (hη_seg i hin hτ)

end Problems.residue_thm
