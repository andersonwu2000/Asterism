import Mathlib

set_option linter.style.longLine false

open Nat Set

namespace Problems.Putnam.putnam_2005_b3

noncomputable abbrev putnam_2005_b3_solution : Set (ℝ → ℝ) := {f : ℝ → ℝ | ∃ᵉ (c > 0) (d > (0 : ℝ)), (d = 1 → c = 1) ∧ (Ioi 0).EqOn f (fun x ↦ c * x ^ d)}

end Problems.Putnam.putnam_2005_b3
