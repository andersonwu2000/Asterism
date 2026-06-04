-- Wrap the parent in strong induction on `i`; the residual inductive step
-- (the IMO core) is shipped as a single Backward sub-goal that takes the
-- strong IH `∀ m < i, m ≤ p-2 → Nat.Prime (m^2+m+p)` as an extra premise.
-- This isolates the substantive arithmetic argument from the structural
-- recursion, which is the standard reduction for IMO 1987 P6 and is
-- strictly simpler than the parent (one fewer ∀ and a richer hypothesis).
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9618

namespace Problems.Minif2f.imo_1987_p6

def prime_quadratic_extension_assuming_prime := @Problems.Minif2f.imo_1987_p6.s9618

end Problems.Minif2f.imo_1987_p6
