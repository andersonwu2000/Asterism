import Mathlib
import Problems.Minif2f.mathd_numbertheory_198.Defs
import Problems.Minif2f.mathd_numbertheory_198.proofs.L_pow5_mod_hundred

namespace Problems.Minif2f.mathd_numbertheory_198

-- `native_decide` injects an axiom (rejected by leaf-bypass), so decompose into the
-- general lemma `∀ n ≥ 2, 5^n % 100 = 25` (provable by `Nat.le_induction` from base
-- `5^2 % 100 = 25` and step `(25*5) % 100 = 25`) and instantiate at n = 2005.
theorem s9265 : 5 ^ 2005 % 100 = 25  := by
  have h_pow5 := pow5_mod_hundred
  exact h_pow5 2005 (by norm_num)

end Problems.Minif2f.mathd_numbertheory_198
