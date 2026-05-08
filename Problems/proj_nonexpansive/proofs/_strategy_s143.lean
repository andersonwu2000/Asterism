import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_limit_to_zero_real
import Problems.proj_nonexpansive.proofs.L_post_division_bound

namespace Problems.proj_nonexpansive

-- Variational inequality via the standard convex-perturbation + limit argument.
-- `post_division_bound` packages: convex combo `(1-t)·Pz + t·w ∈ K`, the
-- minimisation property `‖z - Pz‖ ≤ ‖z - yₜ‖`, the inner-product expansion of
-- `‖z - yₜ‖²`, and division by `t`. Result: for every `t ∈ (0, 1]`,
-- `0 ≤ 2⟨Pz - z, w - Pz⟩ + t·‖w - Pz‖²`. `limit_to_zero_real` is the pure-real
-- limit lemma `(∀ t∈(0,1], 0 ≤ a + t·b) → 0 ≤ a`. Combining yields
-- `0 ≤ 2⟨Pz - z, w - Pz⟩`, and `linarith` halves it.
theorem s143 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ z : X, ∀ w ∈ K, 0 ≤ @inner ℝ X _ (P z - z) (w - P z)  := by
  intro X _ _ K hK_closed hK_conv hK_ne P hP z w hw
  have h_bound : ∀ t : ℝ, 0 < t → t ≤ 1 →
      0 ≤ 2 * @inner ℝ X _ (P z - z) (w - P z) + t * ‖w - P z‖^2 :=
    fun t ht1 ht2 => post_division_bound hK_closed hK_conv hK_ne hP z w hw t ht1 ht2
  have h_two : 0 ≤ 2 * @inner ℝ X _ (P z - z) (w - P z) :=
    limit_to_zero_real _ _ h_bound
  linarith

end Problems.proj_nonexpansive
