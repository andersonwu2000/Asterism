import Mathlib
import Problems.Putnam.putnam_2002_a6.Defs

set_option linter.style.longLine false

open Nat Set Topology Filter

namespace Problems.Putnam.putnam_2002_a6

theorem main : ∀ (f : ℕ → ℕ → ℝ)
(hf : ∀ b : ℕ, f b 1 = 1 ∧ f b 2 = 2 ∧ ∀ n ∈ Ici 3, f b n = n * f b (Nat.digits b n).length),
{b ∈ Ici 2 | ∃ L : ℝ, Tendsto (fun m : ℕ => ∑ n ∈ Finset.Icc 1 m, 1/(f b n)) atTop (𝓝 L)} = putnam_2002_a6_solution := by sorry

end Problems.Putnam.putnam_2002_a6
