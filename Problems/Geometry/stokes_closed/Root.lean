-- Closed-manifold corollary of Stokes: `∫_M dφ = 0` when `Bdry n M` is empty.
-- Rewrite via the Stokes keystone to `∫_∂M (pullbackBdry φ) = 0`, then the
-- boundary integral vanishes because its localCoeff hypothesis is vacuous on
-- the empty boundary (`isEmptyElim`).
import Mathlib
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.DDZero
import Library.Geometry.Manifold.StokesIntegralDefs
import Library.Geometry.ManifoldBoundary.CompactBdry
import Problems.Geometry.stokes_closed.Defs
import Problems.Geometry.stokes_closed.proofs._strategy_s17711

namespace Problems.Geometry.stokes_closed

def main := @Problems.Geometry.stokes_closed.s17711

end Problems.Geometry.stokes_closed
