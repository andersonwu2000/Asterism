-- From f∘f = (·+1987) derive an iterated shift relation, then locate a
-- residue fixed point f(a) ≡ a (mod 1987) (involution on ℤ/1987 is forced
-- to have a fixed point since 1987 is odd). The combinator substitutes
-- f(a) = a + 1987·k into hff(a) via iter_shift, yielding 1 = 2·k → False.
import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs._strategy_s9487

namespace Problems.Minif2f.imo_1987_p4

def no_such_fun := @Problems.Minif2f.imo_1987_p4.s9487

end Problems.Minif2f.imo_1987_p4
