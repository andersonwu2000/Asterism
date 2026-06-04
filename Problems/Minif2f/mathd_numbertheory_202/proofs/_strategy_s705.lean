import Mathlib
import Problems.Minif2f.mathd_numbertheory_202.Defs
import Problems.Minif2f.mathd_numbertheory_202.proofs.L_pow_19_mod_10
import Problems.Minif2f.mathd_numbertheory_202.proofs.L_pow_99_mod_10

namespace Problems.Minif2f.mathd_numbertheory_202

-- Decompose `(19^19 + 99^99) % 10 = 8` into two independent power-mod claims via
-- `Nat.add_mod`. Direct `decide` on the parent reduces a 99-digit power and times out
-- in lake build; `native_decide` is rejected for adding kernel axioms. Splitting lets
-- the Builder pick a smarter strategy (e.g. `Nat.pow_mod` + cyclic 9^2 ≡ 1 mod 10) on
-- the heavy piece `99^99 % 10 = 9`, while the lighter `19^19 % 10 = 9` admits direct
-- kernel reduction. The closer `rw [Nat.add_mod, h1, h2]` finishes since
-- `(9 + 9) % 10` is definitionally `8`.
theorem s705 : (19 ^ 19 + 99 ^ 99) % 10 = 8  := by
  have h1 : 19 ^ 19 % 10 = 9 := pow_19_mod_10
  have h2 : 99 ^ 99 % 10 = 9 := pow_99_mod_10
  rw [Nat.add_mod, h1, h2]

end Problems.Minif2f.mathd_numbertheory_202
