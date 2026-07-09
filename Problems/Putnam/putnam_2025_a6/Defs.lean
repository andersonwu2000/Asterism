import Mathlib

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_2025_a6

def b : ℕ → ℤ
| 0 => 0
| n + 1 => 2 * (b n) ^ 2 + b n + 1

end Problems.Putnam.putnam_2025_a6
