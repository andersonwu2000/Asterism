import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_z_rotation_isometry_family_realizes_matrix
import Problems.Geometry.banach_tarski.proofs.L_zrot_offaxis_collision_set_countable

namespace Problems.Geometry.banach_tarski

-- Reuse the proved z-rotation isometry family (origin-fixing + power law + matrix realization);
-- the only new content is the off-axis collision-countability clause.
-- z_rotation_isometry_family_realizes_matrix supplies R0 with clauses (1),(2) and the matrix
-- realization `hreal`; feed `hreal` into the single sub-goal zrot_offaxis_collision_set_countable
-- (for an off-axis p, the rotated xy-component traces a circle, so {t | R0 t p = q} is countable).
theorem s11457 :
    ∃ R0 : ℝ → (E ≃ᵢ E),
      (∀ t : ℝ, R0 t 0 = 0) ∧
      (∀ (t : ℝ) (n : ℕ), (R0 t) ^ n = R0 ((n : ℝ) * t)) ∧
      (∀ p : E, ¬ (p 0 = 0 ∧ p 1 = 0) → ∀ q : E, {t : ℝ | R0 t p = q}.Countable)  := by
  obtain ⟨R0, h0, hpow, hreal⟩ := z_rotation_isometry_family_realizes_matrix
  refine ⟨R0, h0, hpow, fun p hp q => ?_⟩
  exact zrot_offaxis_collision_set_countable R0 hreal p hp q

end Problems.Geometry.banach_tarski
