import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- zaxis_bad_angles_countable: countable union over countable D of per-point z-axis-collision sets
-- Forward rationale: Grep + Loogle confirmed missing — R1 keywords searched:
-- 'isometry moves countable set off axis', 'origin-fixing isometry off z-axis countable',
-- 'rotation avoids countable directions sphere' (0 reusable mathlib hits).
-- STRATEGY PIVOT: bundled existence deduped against goal 3414; ship the reusable building block
-- the off-axis-mover proof consumes: angles θ where SOME p ∈ D lands on the z-axis form a
-- countable union over countable D, hence countable. Off-axis sibling of bad_angles_countable /
-- scaled_collision_countable; NOT the existence claim, so no dedupe against 3414.
-- Per-point countability carried as hcol, mirroring good_angle_avoids_collisions.
-- entry_kind: Builder
theorem zaxis_bad_angles_countable (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, {θ : ℝ | (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable) :
    {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable := by
  have heq : {θ : ℝ | ∃ p ∈ D, ((R θ) p).ofLp 0 = 0 ∧ ((R θ) p).ofLp 1 = 0} =
      ⋃ p ∈ D, {θ : ℝ | ((R θ) p).ofLp 0 = 0 ∧ ((R θ) p).ofLp 1 = 0} := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_iUnion, exists_prop]
  rw [heq]
  exact hD.biUnion hcol

end Problems.Geometry.banach_tarski
