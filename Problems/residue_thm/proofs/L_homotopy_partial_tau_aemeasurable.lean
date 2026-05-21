-- Decompose AEStronglyMeasurable into ContinuousOn on the open interior,
-- then transfer the restrict-measure from `Ioo 0 1` to `uIoc 0 1 = Ioc 0 1`
-- using `Ioo =ᵐ Ioc` (their symmetric difference is `{1}`, a volume-null set).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10347

namespace Problems.residue_thm

def homotopy_partial_tau_aemeasurable := @Problems.residue_thm.s10347

end Problems.residue_thm
