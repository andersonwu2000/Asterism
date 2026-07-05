-- POU-glue: `inducedOrientFun` is `∑ᶠ q, pou q • chartFun q`; the root is exactly
-- `ContMDiff.finsum_section_of_locallyFinite` applied to that family.
-- Sub-goal 1 (summand_support_locally_finite): the summand supports are locally finite —
-- shrink the POU's own `locallyFinite` along `support_smul_subset_left`.
-- Sub-goal 2 (chartfun_section_contmdiffon_source): each fixed-chart candidate is a
-- `ContMDiffOn` section on its anchor chart's source (P10-mirror fixed-chart argument).
-- Sub-goal 3 (summand_section_contmdiff): upgrade 2 to a globally smooth section after
-- multiplying by the POU bump (`ContMDiffOn.smul_section_of_tsupport`, tsupport ⊆ chart
-- source from the POU's subordination).
import Mathlib
import Problems.Geometry.stokes_induced_orient.Defs
import Problems.Geometry.stokes_induced_orient.proofs._strategy_s11712

namespace Problems.Geometry.stokes_induced_orient

def main := @Problems.Geometry.stokes_induced_orient.s11712

end Problems.Geometry.stokes_induced_orient
