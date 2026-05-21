-- Surjectivity reduces to a single existence sub-goal: for every integer `n`
-- there is a loop `γ_n : Path (1:Circle) 1` whose lift evaluated at 1 equals
-- `n * (2π)`. Combined with `h_char` and cancellation by `2π ≠ 0`, this gives
-- `W' ⟦γ_n⟧ = n`. The existence sub-goal isolates the standard-loop
-- construction (e.g. `Circle.exp ∘ (t ↦ t * n * 2π)`), which is the only
-- non-trivial content remaining; the rest is bookkeeping.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10696

namespace Problems.pi1_circle

def winding_quot_surjective := @Problems.pi1_circle.s10696

end Problems.pi1_circle
