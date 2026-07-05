/-
  Defs.lean — vocabulary for the closed-manifold Stokes corollary `∫_M dφ = 0`.
  Pulls the same manifold / differential-form tower the statement reads:
    * `DiffForm`            (Library.Geometry.Manifold.DiffFormBundle)
    * `mextDeriv`           (Library.Geometry.Manifold.DDZero)
    * `OrientedManifold`, `DiffForm.integral` (Library.Geometry.Manifold.StokesIntegralDefs)
    * `Bdry`                (Library.Geometry.ManifoldBoundary.CompactBdry)
  No new definitions — this problem only states a corollary of the proved Stokes theorem.
-/
import Mathlib
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.DDZero
import Library.Geometry.Manifold.StokesIntegralDefs
import Library.Geometry.ManifoldBoundary.CompactBdry

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_closed

end Problems.Geometry.stokes_closed
