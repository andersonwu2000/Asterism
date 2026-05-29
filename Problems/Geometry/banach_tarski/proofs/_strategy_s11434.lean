import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_scaled_collision_countable

namespace Problems.Geometry.banach_tarski

-- Bad-angle set = ⋃ over n the per-n fiber; split the union over ℕ (Countable).
-- For n=0 the fiber is empty (1 ≤ n fails); for n ≥ 1 it is the D×D-biUnion of
-- the scaled collision sets {θ | R(nθ)p=q}, each countable by sub-goal
-- [scaled_collision_countable] (preimage of hcol's set under θ ↦ nθ, n ≠ 0).
theorem s11434 (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}.Countable  := by
  have hscaled := scaled_collision_countable D R hcol

  have key : {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}
      = ⋃ (n : ℕ), {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} := by
    ext θ; simp only [Set.mem_setOf_eq, Set.mem_iUnion]
  rw [key]
  apply Set.countable_iUnion
  intro n
  by_cases hn : 1 ≤ n
  · have : {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}
        = ⋃ p ∈ D, ⋃ q ∈ D, {θ : ℝ | R ((n : ℝ) * θ) p = q} := by
      ext θ; simp only [Set.mem_setOf_eq, Set.mem_iUnion, hn, true_and]; tauto
    rw [this]
    exact hD.biUnion (fun p hp => hD.biUnion (fun q hq => hscaled n hn p hp q hq))

  · have : {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} = ∅ := by
      ext θ; simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false, not_and]
      intro h; exact absurd h hn
    rw [this]; exact Set.countable_empty


end Problems.Geometry.banach_tarski
