-- Direct: `fderivWithin` of a C² function (one degree lost) is C¹, hence has a Fréchet
-- derivative on the unique-diff product `Icc×Icc`; applying that derivative pointwise at the
-- constant `(1,0)` direction via `HasFDerivWithinAt.clm_apply` (paired with
-- `hasFDerivWithinAt_const`) yields the iterated form, with the `(...).comp 0` summand
-- simped away to leave `.flip (1,0)`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10403

namespace Problems.residue_thm

def fderivwithin_apply10_hasfderivwithinat := @Problems.residue_thm.s10403

end Problems.residue_thm
