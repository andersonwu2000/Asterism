import Mathlib

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_1962_a5

noncomputable abbrev putnam_1962_a5_solution : ℕ → ℕ := fun n : ℕ => n * (n + 1) * 2^(n - 2)

end Problems.Putnam.putnam_1962_a5
