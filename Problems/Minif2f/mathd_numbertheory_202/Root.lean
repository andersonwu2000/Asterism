-- Decompose `(19^19 + 99^99) % 10 = 8` into two independent power-mod claims via
-- `Nat.add_mod`. Direct `decide` on the parent reduces a 99-digit power and times out
-- in lake build; `native_decide` is rejected for adding kernel axioms. Splitting lets
-- the Builder pick a smarter strategy (e.g. `Nat.pow_mod` + cyclic 9^2 ≡ 1 mod 10) on
-- the heavy piece `99^99 % 10 = 9`, while the lighter `19^19 % 10 = 9` admits direct
-- kernel reduction. The closer `rw [Nat.add_mod, h1, h2]` finishes since
-- `(9 + 9) % 10` is definitionally `8`.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_202.Defs
import Problems.Minif2f.mathd_numbertheory_202.proofs._strategy_s705

namespace Problems.Minif2f.mathd_numbertheory_202

def main := @Problems.Minif2f.mathd_numbertheory_202.s705

end Problems.Minif2f.mathd_numbertheory_202
