import Mathlib
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.PullbackFlatDNat         -- pullbackFlatForm

/-!
Setup for the **LF-continuity crux** of the de Rham integration current. The final
unfinished piece of the currents bridge is upgrading `[[e]] : ψ ↦ ∫_N e* ψ` to a genuine
*continuous* functional (a `Current = 𝓓(Ω, Λ) →L ℝ`). By `TestFunction.limitCLM` /
`continuous_of_isBounded`, continuity reduces to a per-compact `C⁰` boundedness estimate
on the integral. This problem isolates that estimate; it is the one genuinely-new analytic
lemma of the bridge (no existing bound on `DiffForm.integral` in Library or Mathlib).
-/

open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open scoped Manifold Bundle ContDiff

namespace Problems.Geometry.integration_current_bounded
end Problems.Geometry.integration_current_bounded
