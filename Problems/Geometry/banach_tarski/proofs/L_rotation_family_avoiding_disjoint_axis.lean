import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Forward rationale: Grep + Loogle confirmed missing — no 1-parameter ℝ³ rotation
-- family in mathlib carrying the (R θ)^n = R(nθ) power law together with the
-- per-pair countable-collision property. This is the geometric heart of the
-- Hilbert-hotel absorption: given a countable D, pick an axis u off D, rotate
-- about u. Power law = SO(2) angle additivity; countable collisions because for
-- fixed p,q the equation R θ p = q pins θ to one residue mod 2π (axis-off-D kills
-- the degenerate p=q on the axis). Reuses orthogonal_matrix_isometry_equiv /
-- orthogonal_matrix_preserves_inner for the SO(2)-block → E ≃ᵢ E bridge.
-- entry_kind: Backward
theorem rotation_family_avoiding_disjoint_axis (D : Set E) (hD : D.Countable) :
    ∃ R : ℝ → (E ≃ᵢ E),
      (∀ θ : ℝ, R θ 0 = 0) ∧
      (∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ)) ∧
      (∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) := by
  sorry

end Problems.Geometry.banach_tarski
