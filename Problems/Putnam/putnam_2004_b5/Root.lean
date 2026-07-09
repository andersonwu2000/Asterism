import Mathlib
import Problems.Putnam.putnam_2004_b5.Defs

set_option linter.style.longLine false

open Nat Topology Filter

namespace Problems.Putnam.putnam_2004_b5

theorem main : ∀ (xprod : ℝ → ℝ)
    (hxprod : ∀ x ∈ Set.Ioo 0 1,
      Tendsto (fun N ↦ ∏ n ∈ Finset.range N, ((1 + x ^ (n + 1)) / (1 + x ^ n)) ^ (x ^ n))
      atTop (𝓝 (xprod x))),
Tendsto xprod (𝓝[<] 1) (𝓝 putnam_2004_b5_solution) := by sorry

end Problems.Putnam.putnam_2004_b5
