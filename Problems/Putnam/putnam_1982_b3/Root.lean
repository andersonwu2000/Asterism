import Mathlib
import Problems.Putnam.putnam_1982_b3.Defs

set_option linter.style.longLine false

open Set Function Filter Topology Polynomial Real

namespace Problems.Putnam.putnam_1982_b3

theorem main : ∀ (p : ℕ → ℝ)
(hp : p = fun n : ℕ => ({(c, d) : Finset.Icc 1 n × Finset.Icc 1 n | ∃ m : ℕ, m^2 = c + d}.ncard : ℝ) / n^2),
Tendsto (fun n : ℕ => p n * Real.sqrt n) atTop (𝓝 putnam_1982_b3_solution) := by sorry

end Problems.Putnam.putnam_1982_b3
