import Mathlib
import Problems.Minif2f.mathd_numbertheory_236.Defs

namespace Problems.Minif2f.mathd_numbertheory_236

-- Direct closure: `1999 ^ 2000 % 5 = 1` via kernel-only modular arithmetic
-- (no `native_decide` — it introduces a rogue native-compilation axiom).
-- Strategy: rewrite `2000 = 2 * 1000`, apply `pow_mul` and `Nat.pow_mod`,
-- reduce `1999 ^ 2 % 5 = 1` by `decide` (small kernel check), then `one_pow`
-- collapses `1 ^ 1000` to `1`, leaving `1 % 5 = 1` closed by `rfl`.
theorem s9307 : 1999 ^ 2000 % 5 = 1  := by
  have h : (1999 : ℕ)^2 % 5 = 1 := by decide
  rw [show (2000 : ℕ) = 2 * 1000 from rfl, pow_mul, Nat.pow_mod, h, one_pow]
  rfl

end Problems.Minif2f.mathd_numbertheory_236
