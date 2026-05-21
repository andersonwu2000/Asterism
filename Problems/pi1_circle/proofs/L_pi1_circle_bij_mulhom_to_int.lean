-- Strip the `Multiplicative ℤ` wrapping to an additive winding function
-- `W : FundamentalGroup Circle 1 → ℤ` with the three monoid-relevant properties
-- (W 1 = 0, W (a*b) = W a + W b, bijective); the combinator packages those into a
-- bijective MonoidHom via `Multiplicative.ofAdd ∘ W`. Sub-goal isolates the winding
-- construction (Forward bricks + monodromy_*); combinator is pure plumbing.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10689

namespace Problems.pi1_circle

def pi1_circle_bij_mulhom_to_int := @Problems.pi1_circle.s10689

end Problems.pi1_circle
