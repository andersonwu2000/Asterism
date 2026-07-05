-- Mirror `contMDiff_pullbackBdryFun`: prove the section into the form-bundle total space is
-- smooth pointwise. At each `p0`, read the section through the trivialization at `p0`
-- (`contMDiffAt_section_iff`), then `congr_of_eventuallyEq` the trivialization read to the
-- fixed-basepoint coordinate formula valid on the chart source.
--   • pullback_flat_fixed_chart_contmdiff_at — the fixed-chart coordinate formula is smooth
--     at `p0` (cites the proved analytic core s17802).
--   • pullback_flat_triv_read — on the chart source the trivialization read of
--     `pullbackFlatFormFun` equals that fixed-chart formula (coord-change naturality crux).
import Mathlib
import Problems.Geometry.pullback_flat_form.Defs
import Problems.Geometry.pullback_flat_form.proofs._strategy_s17804

namespace Problems.Geometry.pullback_flat_form

def main := @Problems.Geometry.pullback_flat_form.s17804

end Problems.Geometry.pullback_flat_form
