import Mathlib

set_option linter.style.longLine false

open Set Nat Function

namespace Problems.Putnam.putnam_2007_b4

noncomputable abbrev putnam_2007_b4_solution : ℕ → ℕ := fun n ↦ 2 ^ (n + 1)

end Problems.Putnam.putnam_2007_b4
