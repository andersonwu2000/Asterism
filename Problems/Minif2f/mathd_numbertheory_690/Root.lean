-- Direct: membership of 314 is `decide`d per conjunct; lower bound unfolds
-- `Nat.ModEq` to `% =` form and discharges via `omega` (handles modular linear
-- arithmetic, deriving a + 1 ≡ 0 mod {3,5,7,9} hence a ≥ 314 from 0 < a).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_690.Defs
import Problems.Minif2f.mathd_numbertheory_690.proofs._strategy_s742

namespace Problems.Minif2f.mathd_numbertheory_690

def main := @Problems.Minif2f.mathd_numbertheory_690.s742

end Problems.Minif2f.mathd_numbertheory_690
