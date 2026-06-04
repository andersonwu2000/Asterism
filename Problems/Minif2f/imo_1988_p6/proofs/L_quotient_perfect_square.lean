-- WLOG reduction: a' ^ 2 + b' ^ 2 and a' * b' are symmetric in (a', b'); swap on
-- a' ≤ b' lets us assume b ≤ a, which is the precondition the descent argument needs.
-- vieta_descent_le carries the substantive Vieta-jumping descent under that order.
import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs._strategy_s9449

namespace Problems.Minif2f.imo_1988_p6

def quotient_perfect_square := @Problems.Minif2f.imo_1988_p6.s9449

end Problems.Minif2f.imo_1988_p6
