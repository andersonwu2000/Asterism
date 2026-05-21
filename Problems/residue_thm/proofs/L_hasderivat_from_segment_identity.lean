-- Pass ContinuousOn Q on the punctured set (rather than the prior dead s10532's
-- ContinuousAt-only hypothesis) so the parametric integrand
-- `t ↦ Q (z + t·h)` is continuous, hence AEStronglyMeasurable on [0,1] — the
-- precise gap the previous decomposition declined on.
-- (1) continuous_on_punctured_of_analytic — Builder, AnalyticOn ⇒ ContinuousOn.
-- (2) hasderivat_from_continuous_on_segment_identity — Backward analytic core:
--     ContinuousOn Q on punctured + segment identity ⇒ HasDerivAt F (Q z) z.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10618

namespace Problems.residue_thm

def hasderivat_from_segment_identity := @Problems.residue_thm.s10618

end Problems.residue_thm
