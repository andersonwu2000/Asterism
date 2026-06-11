-- Direct proof: the map is a continuous multilinear map composed with the diagonal CLM,
-- hence continuously polynomial, hence C^n via `CPolynomialAt.contDiffAt` —
-- bypassing `ContDiff.comp` whose instance unification times out here (per problem lessons).
import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs._strategy_s11684

namespace Problems.Geometry.stokes_form_bundle

def comp_diag_multilinear_contdiff := @Problems.Geometry.stokes_form_bundle.s11684

end Problems.Geometry.stokes_form_bundle
