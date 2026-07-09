import Mathlib

set_option linter.style.longLine false

open MeasureTheory Set

namespace Problems.Putnam.putnam_1962_a2

noncomputable abbrev putnam_1962_a2_solution : Set (ℝ → ℝ) := {f | (∃ a c : ℝ, 0 ≤ a ∧ f = (fun x : ℝ ↦ a / (1 - c * x) ^ 2)) ∨ (∃ a c : ℝ, 0 ≤ a ∧ 0 < c ∧ f = (fun x : ℝ ↦ if x < 1 / c then a / (1 - c * x) ^ 2 else 0)) ∨ (0 ≤ f ∧ ∀ x : ℝ, 0 < x → f x = 0) ∨ (∃ e : ℝ, 0 < e ∧ f 0 = 0 ∧ 0 ≤ f ∧ ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0)}

end Problems.Putnam.putnam_1962_a2
