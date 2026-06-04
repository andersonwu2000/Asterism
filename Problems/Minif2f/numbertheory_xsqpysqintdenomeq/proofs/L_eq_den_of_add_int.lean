-- Decompose `(a+b).den = 1 ⇒ a.den = b.den` via "a+b is an integer".
-- `den_one_eq_int` extracts the integer witness n with a+b = ↑n;
-- `intcast_sub_den` says (↑n - a).den = a.den (subtracting a rational
-- from an integer preserves the denominator). Combine: b = ↑n - a, so
-- b.den = (↑n - a).den = a.den.
import Mathlib
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.Defs
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.proofs._strategy_s9352

namespace Problems.Minif2f.numbertheory_xsqpysqintdenomeq

def eq_den_of_add_int := @Problems.Minif2f.numbertheory_xsqpysqintdenomeq.s9352

end Problems.Minif2f.numbertheory_xsqpysqintdenomeq
