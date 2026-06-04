import Mathlib
namespace Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3

-- two_cube_sum_factored: ring identity 2(x³+y³+z³) - xyz(x+y+z+6) = (x+y+z)·(hyp-lhs - xyz),
-- zeroed by the hypothesis; conclude by linarith after mul_eq_zero_of_right.
theorem two_cube_sum_factored :
    ∀ (x y z : ℤ),
      (x - y) ^ 2 + (y - z) ^ 2 + (z - x) ^ 2 = x * y * z →
        2 * (x ^ 3 + y ^ 3 + z ^ 3) = x * y * z * (x + y + z + 6) := by
  intro x y z h
  have key : 2 * (x ^ 3 + y ^ 3 + z ^ 3) - x * y * z * (x + y + z + 6) =
      (x + y + z) * ((x - y) ^ 2 + (y - z) ^ 2 + (z - x) ^ 2 - x * y * z) := by ring
  have hzero : (x - y) ^ 2 + (y - z) ^ 2 + (z - x) ^ 2 - x * y * z = 0 := by linarith
  linarith [mul_eq_zero_of_right (x + y + z) hzero]

end Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3
