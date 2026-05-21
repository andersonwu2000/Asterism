-- Decompose path-reversal sign-flip into (a) chain rule + a.e. swap so the LHS becomes
-- `-(∫ Q(β(1-t)) * deriv β (1-t))` and (b) substitution `u = 1 - t` equating the
-- two unsigned integrals.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10546

namespace Problems.residue_thm

def path_reverse_integral_eq_neg := @Problems.residue_thm.s10546

end Problems.residue_thm
