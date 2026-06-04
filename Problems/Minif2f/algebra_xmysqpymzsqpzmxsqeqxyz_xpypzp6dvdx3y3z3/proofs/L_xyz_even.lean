import Mathlib
import Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3.Defs

namespace Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3

-- xyz_even: LHS expands to 2*(x²+y²+z²-xy-yz-zx) by ring, so xyz is even.
theorem xyz_even :
    ∀ (x y z : ℤ),
      (x - y) ^ 2 + (y - z) ^ 2 + (z - x) ^ 2 = x * y * z →
        ∃ k : ℤ, x * y * z = 2 * k := by
  intro x y z h
  use x ^ 2 + y ^ 2 + z ^ 2 - x * y - y * z - z * x
  have : (x - y) ^ 2 + (y - z) ^ 2 + (z - x) ^ 2 =
         2 * (x ^ 2 + y ^ 2 + z ^ 2 - x * y - y * z - z * x) := by ring
  linarith

end Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3
