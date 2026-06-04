-- `native_decide` injects an axiom (rejected by leaf-bypass), so decompose into the
-- general lemma `∀ n ≥ 2, 5^n % 100 = 25` (provable by `Nat.le_induction` from base
-- `5^2 % 100 = 25` and step `(25*5) % 100 = 25`) and instantiate at n = 2005.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_198.Defs
import Problems.Minif2f.mathd_numbertheory_198.proofs._strategy_s9265

namespace Problems.Minif2f.mathd_numbertheory_198

def main := @Problems.Minif2f.mathd_numbertheory_198.s9265

end Problems.Minif2f.mathd_numbertheory_198
