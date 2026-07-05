import Mathlib

/-!
Shared setup for `pullback_flat_smooth` — the analytic heart of the
integration-current bridge's first brick (`pullbackFlatForm`).

A *flat test `k`-form* on an ambient normed space `F` is a smooth field
`φ : F → (F [⋀^Fin k]→L[ℝ] ℝ)`.  Its pullback along a smooth map `e : E → F`
has coordinate representative
  `x ↦ (φ (e x)).compContinuousLinearMap (fderiv ℝ e x)`.
No new definitions are fixed here; the Root states the smoothness of that
representative.  Unlike the boundary inclusion — whose coordinate derivative is
the *constant* `faceEmbedL` — here `fderiv ℝ e x` varies with `x`, which is the
one genuinely new analytic ingredient over the existing boundary pullback.
-/

namespace Problems.Geometry.pullback_flat_smooth

end Problems.Geometry.pullback_flat_smooth
