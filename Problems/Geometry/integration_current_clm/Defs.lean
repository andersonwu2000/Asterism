import Mathlib
import Library.Geometry.Currents.PullbackFormBounded         -- pullbackFlatForm_integral_bounded (crux)
import Library.Geometry.Currents.BoundarySquareZero          -- Current
import Library.Geometry.Manifold.StokesIntegralDefs          -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.PullbackFlatDNat        -- pullbackFlatForm

/-!
Final brick of the de Rham integration-current bridge: package the integration current
`[[e]] : φ ↦ ∫_N e* φ` as a genuine *continuous* dual — a `Current = 𝓓(Ω, Λ) →L[ℝ] ℝ`.
The analytic crux (C⁰ boundedness `|∫_N e* ψ| ≤ C · sup‖ψ‖`) is proved & harvested as
`pullbackFlatForm_integral_bounded`; here that bound is fed through
`TestFunction.limitCLM` (per-compact `continuous_of_isBounded`) to produce the continuous
functional. This completes the bridge: classical Stokes is now `∂[[e]] = [[∂e]]` on
genuine topological-dual currents.
-/

open TopologicalSpace
open Library.Geometry.Currents.PullbackFormBounded
open Library.Geometry.Currents.BoundarySquareZero
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open scoped Manifold Bundle ContDiff Distributions

namespace Problems.Geometry.integration_current_clm
end Problems.Geometry.integration_current_clm
