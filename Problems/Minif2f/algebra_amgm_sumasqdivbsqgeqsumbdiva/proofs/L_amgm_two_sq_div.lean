import Mathlib
import Problems.Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva.Defs

namespace Problems.Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva

-- amgm_two_sq_div: AM-GM via perfect-square identity (x/y - y/z)^2 ≥ 0
theorem amgm_two_sq_div : ∀ (x y z : ℝ), 0 < x → 0 < y → 0 < z →
    x ^ 2 / y ^ 2 + y ^ 2 / z ^ 2 ≥ 2 * (x / z) := by
  intro x y z hx hy hz
  rw [ge_iff_le, ← sub_nonneg]
  have key : x ^ 2 / y ^ 2 + y ^ 2 / z ^ 2 - 2 * (x / z) =
    (x / y - y / z) ^ 2 := by field_simp; ring
  linarith [sq_nonneg (x / y - y / z), key.symm.le]

end Problems.Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva
