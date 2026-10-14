import Mathlib
import Problems.Geometry.pullback_flat_dnat.Defs
import Problems.Geometry.pullback_flat_dnat.proofs.L_coord_rep_pullback
import Problems.Geometry.pullback_flat_form.proofs.L_pullback_flat_fderiv_within_chart_contdiffon
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_integral.Defs
import Problems.Geometry.stokes_mextderiv.Defs

/-!
Setup for the **LF-continuity crux** of the de Rham integration current. The final
unfinished piece of the currents bridge is upgrading `[[e]] : ψ ↦ ∫_N e* ψ` to a genuine
*continuous* functional (a `Current = 𝓓(Ω, Λ) →L ℝ`). By `TestFunction.limitCLM` /
`continuous_of_isBounded`, continuity reduces to a per-compact `C⁰` boundedness estimate
on the integral. This problem isolates that estimate; it is the one genuinely-new analytic
lemma of the bridge (no existing bound on `DiffForm.integral` in Library or Mathlib).
-/

open scoped Manifold Bundle ContDiff

namespace Problems.Geometry.integration_current_bounded
end Problems.Geometry.integration_current_bounded
