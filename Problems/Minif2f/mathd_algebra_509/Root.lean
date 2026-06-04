-- Reduce √(E) = 13/6 by first simplifying the inner expression E to 169/36
-- (folding √80=4√5, √845=13√5, √45=3√5 and the /√5 division), then evaluating
-- √(169/36) = 13/6.  Both sub-goals are arithmetic / sqrt-eval, simpler than the
-- whole nested-radical equation.
import Mathlib
import Problems.Minif2f.mathd_algebra_509.Defs
import Problems.Minif2f.mathd_algebra_509.proofs._strategy_s680

namespace Problems.Minif2f.mathd_algebra_509

def main := @Problems.Minif2f.mathd_algebra_509.s680

end Problems.Minif2f.mathd_algebra_509
