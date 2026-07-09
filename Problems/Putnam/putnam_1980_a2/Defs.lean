import Mathlib

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_1980_a2

noncomputable abbrev putnam_1980_a2_solution : ℕ → ℕ → ℕ := (fun r s : ℕ => (1 + 4 * r + 6 * r ^ 2) * (1 + 4 * s + 6 * s ^ 2))

end Problems.Putnam.putnam_1980_a2
