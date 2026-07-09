import Mathlib

set_option linter.style.longLine false

open Nat Set

namespace Problems.Putnam.putnam_2005_a2

noncomputable abbrev putnam_2005_a2_solution : ℕ → ℕ := fun n ↦ if n = 1 then 0 else 2 ^ (n - 2)

end Problems.Putnam.putnam_2005_a2
