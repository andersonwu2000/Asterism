-- Decompose by abstracting `h := the piecewise integral primitive` and showing
-- (1) `h` is C¹ on `Icc 0 1` (wrapper for proved `flat_concat_ftc_smooth`);
-- (2) `h t = β' (2t - 1)` pointwise on `Icc (1/2) 1`
--     (combining left-half FTC eval `α' 1 - α' 0` with right-half eval
--      `β' (2t-1) - β' 0` and `h_match : α' 1 = β' 0` cancels the constant);
-- (3) the abstract substitution `u = 2t - 1` taking
--     `∫_(1/2)^1 Q (h t) * deriv h t = ∫_0^1 Q (β' t) * deriv β' t`
--     for any C¹ `h` agreeing with `β' (2t-1)` on the right half.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10670

namespace Problems.residue_thm

def flat_ftc_right_half_int_eq := @Problems.residue_thm.s10670

end Problems.residue_thm
