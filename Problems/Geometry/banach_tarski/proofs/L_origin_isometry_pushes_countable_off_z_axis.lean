import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Forward rationale: Grep + Loogle confirmed missing (searched: `LinearIsometryEquiv ?v = ?w`,
-- isometry/rotation sending one unit vector to another, countability of forbidden directions on
-- the sphere) — no single mathlib lemma exists; custom cardinality + frame-isometry brick.
-- Rebuilds the DEAD `isometry_moves_countable_off_axis` (s11435 over-scoped). Kept TIGHT:
-- one origin-fixing isometry whose image of every point of a countable set is off the z-axis,
-- conclusion stated as a plain coordinate inequality (`¬ (coord0 = 0 ∧ coord1 = 0)`), no match,
-- no extra rotation-family / power structure. Used by the Hilbert-hotel step to free the
-- countable fixed-point set from the rotation axis.
-- entry_kind: Backward
theorem origin_isometry_pushes_countable_off_z_axis
    (D : Set E) (hD : D.Countable) :
    ∃ g : E ≃ᵢ E, g 0 = 0 ∧ ∀ p ∈ D, ¬ ((g p) 0 = 0 ∧ (g p) 1 = 0) := by
  sorry

end Problems.Geometry.banach_tarski
