import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Forward rationale: brick 2 of the settled crux assembly. Given a countable set D of
-- points, there is an origin-fixing self-isometry g of ℝ³ that moves every point of D
-- off the z-axis (i.e. away from the locus {x | x 0 = 0 ∧ x 1 = 0}). Pure cardinality:
-- the set of frame choices whose axis hits some point of D is countable, while the
-- sphere of frame directions is uncountable, so a good g exists. Realizes the chosen
-- direction as an origin-fixing frame isometry. Rebuild of the dead
-- `isometry_moves_countable_off_axis` / `origin_isometry_pushes_countable_off_z_axis`,
-- kept TIGHT (∃-form, no named noncomputable def) to avoid the over-scoping that killed them.
-- entry_kind: Backward
theorem off_axis_mover (D : Set E) (hD : D.Countable) :
    ∃ g : E ≃ᵢ E, g 0 = 0 ∧ ∀ p ∈ D, ¬ ((g p) 0 = 0 ∧ (g p) 1 = 0) := by sorry

end Problems.Geometry.banach_tarski
