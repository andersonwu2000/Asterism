-- Three-step Hilbert argument: variational ineq → norm-sq inner bound → Cauchy-Schwarz.
-- s1: t→0⁺ limit gives ⟪Px-x, y-Px⟫≥0; s2: add at x and y; s3: abstract norm cancellation.
import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_inner_sq_bound
import Problems.proj_nonexpansive.proofs.L_norm_le_of_inner_sq_le
import Problems.proj_nonexpansive.proofs.L_variational_ineq

open scoped InnerProductSpace

namespace Problems.proj_nonexpansive

theorem s11 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖  := by
  intro X _instNACG _instIPS K hK hConv hNE P hP x y
  have h_var : ∀ z (w : X), w ∈ K → ⟪P z - z, w - P z⟫_ℝ ≥ 0 :=
    fun z w hw => variational_ineq hK hConv hNE hP z w hw
  have h_inner : ‖P x - P y‖ ^ 2 ≤ ⟪x - y, P x - P y⟫_ℝ :=
    inner_sq_bound (fun z => (hP z).1) h_var x y
  exact norm_le_of_inner_sq_le (P x - P y) (x - y) h_inner

end Problems.proj_nonexpansive
