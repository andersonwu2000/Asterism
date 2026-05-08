import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- post_division_arith: expand ‖a - t•b‖² via `norm_sub_sq_real`, factor t, divide.
-- Set a = z - P z, b = w - P z. The hypothesis ‖a‖² ≤ ‖a - t•b‖² combined with
-- the identity ‖a - t•b‖² = ‖a‖² - 2t⟪a,b⟫ + t²‖b‖² (using `norm_sub_sq_real`,
-- `inner_smul_right`, `norm_smul`, `sq_abs`) gives 0 ≤ t·(-2⟪a,b⟫ + t‖b‖²).
-- Since t > 0, divide to get 0 ≤ -2⟪a,b⟫ + t‖b‖²; then `inner_neg_left` flips
-- ⟪P z - z, w - P z⟫ = -⟪a,b⟫ and `linarith` closes the goal.
theorem post_division_arith :
    ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
      {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
      ∀ {P : X → X}, IsMetricProjector K P →
      ∀ z : X, ∀ w ∈ K, ∀ t : ℝ, 0 < t → t ≤ 1 →
      ‖z - P z‖^2 ≤ ‖(z - P z) - t • (w - P z)‖^2 →
      0 ≤ 2 * @inner ℝ X _ (P z - z) (w - P z) + t * ‖w - P z‖^2 := by
  intro X _ _ K _ _ _ P _ z w hwK t ht0 ht1 hsq
  have hexp : ‖(z - P z) - t • (w - P z)‖^2
            = ‖z - P z‖^2 - 2 * (t * @inner ℝ X _ (z - P z) (w - P z))
              + t^2 * ‖w - P z‖^2 := by
    rw [norm_sub_sq_real, inner_smul_right, norm_smul, Real.norm_eq_abs]
    ring_nf
    rw [sq_abs]
  rw [hexp] at hsq
  have h0 : 0 ≤ -(2 * (t * @inner ℝ X _ (z - P z) (w - P z))) + t^2 * ‖w - P z‖^2 := by
    linarith
  have hfac : -(2 * (t * @inner ℝ X _ (z - P z) (w - P z))) + t^2 * ‖w - P z‖^2
            = t * (-(2 * @inner ℝ X _ (z - P z) (w - P z)) + t * ‖w - P z‖^2) := by ring
  rw [hfac] at h0
  have hsign : 0 ≤ -(2 * @inner ℝ X _ (z - P z) (w - P z)) + t * ‖w - P z‖^2 := by
    by_contra hc
    have hc' : -(2 * @inner ℝ X _ (z - P z) (w - P z)) + t * ‖w - P z‖^2 < 0 :=
      lt_of_not_ge hc
    have hneg : t * (-(2 * @inner ℝ X _ (z - P z) (w - P z)) + t * ‖w - P z‖^2) < 0 :=
      mul_neg_of_pos_of_neg ht0 hc'
    linarith
  have hflip : @inner ℝ X _ (P z - z) (w - P z) = -(@inner ℝ X _ (z - P z) (w - P z)) := by
    rw [show (P z - z : X) = -(z - P z) from by abel, inner_neg_left]
  linarith

end Problems.proj_nonexpansive
