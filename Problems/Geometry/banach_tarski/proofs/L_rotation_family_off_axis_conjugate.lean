import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Forward rationale: Fresh slug for the dead (A) statement — prior slug
-- `rotation_family_avoiding_disjoint_axis` collides on disk (its dead proof file
-- persists, blocking re-injection). SAME statement, byte-identical clauses; only the
-- name changes, so goal 3410's closer must now cite `rotation_family_off_axis_conjugate`.
-- Thin ASSEMBLY: conjugate the z-axis collision family R₀ (from `zrot_collision_family`)
-- by `g` (from `exists_isometry_moving_off_zaxis D hD`): R θ := g⁻¹ * R₀ θ * g.
-- Fixes 0 (g, R₀ fix 0); power law via conjugation being a group hom; collisions
-- countable since g moves every p ∈ D off the z-axis, feeding R₀'s off-axis clause.
-- No new mathematics — pure conjugation transport.
-- entry_kind: Backward
theorem rotation_family_off_axis_conjugate (D : Set E) (hD : D.Countable) :
    ∃ R : ℝ → (E ≃ᵢ E),
      (∀ θ : ℝ, R θ 0 = 0) ∧
      (∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ)) ∧
      (∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) := by
  sorry

end Problems.Geometry.banach_tarski
