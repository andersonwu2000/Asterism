import Mathlib

set_option linter.style.longLine false

open Filter Topology

namespace Problems.Putnam.putnam_1994_b1

noncomputable abbrev putnam_1994_b1_solution : Set ℤ := {n : ℤ | (315 ≤ n ∧ n ≤ 325) ∨ (332 ≤ n ∧ n ≤ 350)}

end Problems.Putnam.putnam_1994_b1
