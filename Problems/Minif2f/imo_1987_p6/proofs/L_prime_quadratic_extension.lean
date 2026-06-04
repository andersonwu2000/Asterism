-- Decompose into two sub-goals: (1) the hypothesis at k=0 forces `Nat.Prime p`,
-- (2) with `Nat.Prime p` in scope, derive the conclusion (this is the IMO core).
-- Sub-goal (1) is a true leaf (instantiate the universal at k=0). Sub-goal (2)
-- is the residual IMO 1987 P6 statement with one extra fact (`p` prime) added.
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9436

namespace Problems.Minif2f.imo_1987_p6

def prime_quadratic_extension := @Problems.Minif2f.imo_1987_p6.s9436

end Problems.Minif2f.imo_1987_p6
