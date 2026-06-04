-- Strong induction on `a` (Nat.strong_induction_on). Dispatch on `b ≤ a`:
-- if b = a, equal_case forces a = 1, k = 1; if b < a, vieta_step either exhibits
-- the square directly or produces an order-preserving Vieta jump (c, d) with c < a,
-- which the strong IH closes.
import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs._strategy_s9629

namespace Problems.Minif2f.imo_1988_p6

def vieta_descent_le := @Problems.Minif2f.imo_1988_p6.s9629

end Problems.Minif2f.imo_1988_p6
