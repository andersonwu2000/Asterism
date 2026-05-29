import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Forward rationale: Brief's AXIS-CHOICE brick. Given a countable D ⊆ ℝ³, produce an
-- origin-fixing isometry g moving all of D off the z-axis ({p | p 0 = 0 ∧ p 1 = 0}).
-- Route (Strategist): pick a unit u with D avoiding the line ℝ∙u by a pure cardinality
-- argument (countably many lines vs uncountable sphere, reusing freegroup_range_countable /
-- bad_angles_countable style complement machinery), then conjugate by a frame isometry
-- sending u to e₂. Generic over any countable D; the key reusable axis-selection step.
-- entry_kind: Backward
theorem isometry_moves_countable_off_axis
    (D : Set E) (hD : D.Countable) :
    ∃ g : E ≃ᵢ E, g 0 = 0 ∧ ∀ p ∈ D, ¬ ((g p) 0 = 0 ∧ (g p) 1 = 0) := by
  sorry

end Problems.Geometry.banach_tarski
