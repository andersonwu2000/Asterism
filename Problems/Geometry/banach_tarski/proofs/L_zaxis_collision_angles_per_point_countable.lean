-- Witness Q = rotation about the x-axis, realized from the orthogonal block
-- !![1,0,0; 0,cos φ,-sin φ; 0,sin φ,cos φ] via PROVED orthogonal_matrix_isometry_equiv.
-- Two sub-goals: (1) x_rotation_block_orthogonal — that block satisfies Mᵀ·M = 1
-- (Builder entry computation); (2) x_rotation_collision_countable — for the realized
-- family, every off-origin p has a countable z-axis-collision angle set (Backward:
-- (Q φ p) 0 = p 0 is φ-independent, so p 0 ≠ 0 ⟹ ∅; p 0 = 0 ⟹ (p 1,p 2) ≠ 0 and
-- cos φ·p 1 - sin φ·p 2 = 0 cuts a discrete set). `choose` extracts Q from the per-φ
-- realization; origin clause is `rw [hQ φ 0]; simp` (the realization is linear).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11447

namespace Problems.Geometry.banach_tarski

def zaxis_collision_angles_per_point_countable := @Problems.Geometry.banach_tarski.s11447

end Problems.Geometry.banach_tarski
