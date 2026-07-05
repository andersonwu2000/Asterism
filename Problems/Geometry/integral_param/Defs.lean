/-
  Defs.lean — vocabulary for the multi-chart density transition law
  `localCoeff g x = det(transition') * (localCoeff g x₀ ∘ transition)`.

  No NEW definitions: reuses the Library's `localCoeff` / `topCoeff` / `formInCoord` and the
  proved differential-form chart-transition law `form_in_coord_pullback`. None of these pulls in
  the heavy Stokes proof tower, so init + cold builds stay fast.
-/
import Mathlib
import Library.Geometry.Manifold.DiffFormBundle          -- DiffForm
import Library.Geometry.Manifold.MExtDerivCoord           -- formInCoord, form_in_coord_pullback
import Library.Geometry.Manifold.StokesIntegralDefs       -- localCoeff, topCoeff

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs

namespace Problems.Geometry.integral_param

end Problems.Geometry.integral_param
