import Mathlib
import Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3.Defs
import Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3.proofs.L_two_cube_sum_factored
import Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3.proofs.L_xyz_even

namespace Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3

-- Decompose divisibility into ring identity `2(x³+y³+z³) = xyz·(x+y+z+6)`
-- plus parity `∃ k, xyz = 2k`; substitute and cancel the 2 via linarith.
theorem s781 : ∀ (x y z : ℤ) (h₀ : (x - y) ^ 2 + (y - z) ^ 2 + (z - x) ^ 2 = x * y * z), x + y + z + 6 ∣ x ^ 3 + y ^ 3 + z ^ 3  := by
  intro x y z h₀
  have h_id := two_cube_sum_factored x y z h₀
  have h_par := xyz_even x y z h₀
  obtain ⟨k, hk⟩ := h_par
  refine ⟨k, ?_⟩
  have h2 : 2 * (x^3 + y^3 + z^3) = 2 * ((x + y + z + 6) * k) := by
    linear_combination h_id + (x + y + z + 6) * hk
  linarith

end Problems.Minif2f.algebra_xmysqpymzsqpzmxsqeqxyz_xpypzp6dvdx3y3z3
