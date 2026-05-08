import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- norm_sq_le_inner_diff: add the variational inequalities at x and y to obtain
-- ‖P x - P y‖² ≤ ⟨x - y, P x - P y⟩.
-- Apply hVar at z = x with w = P y ∈ K and at z = y with w = P x ∈ K, giving
-- 0 ≤ ⟨P x - x, P y - P x⟩ and 0 ≤ ⟨P y - y, P x - P y⟩. Rewrite P y - P x as
-- -(P x - P y) and combine with `inner_sub_left` so that the cross terms collapse
-- to ⟨(x - y) - (P x - P y), P x - P y⟩ ≥ 0; finally identify
-- ⟨P x - P y, P x - P y⟩ with ‖P x - P y‖² via `real_inner_self_eq_norm_sq`.
theorem norm_sq_le_inner_diff : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  (∀ z : X, ∀ w ∈ K, 0 ≤ @inner ℝ X _ (P z - z) (w - P z)) →
  ∀ x y : X, ‖P x - P y‖^2 ≤ @inner ℝ X _ (x - y) (P x - P y) := by
  intro X _ _ K _ _ _ P hP hVar x y
  have hPxK : P x ∈ K := (hP x).1
  have hPyK : P y ∈ K := (hP y).1
  have h1 : 0 ≤ @inner ℝ X _ (P x - x) (P y - P x) := hVar x (P y) hPyK
  have h2 : 0 ≤ @inner ℝ X _ (P y - y) (P x - P y) := hVar y (P x) hPxK
  have hkey : @inner ℝ X _ (P x - P y) (P x - P y) ≤ @inner ℝ X _ (x - y) (P x - P y) := by
    have hPyPx : (P y - P x : X) = -(P x - P y) := by abel
    rw [hPyPx, inner_neg_right] at h1
    have hcombo : 0 ≤ @inner ℝ X _ (P y - y) (P x - P y)
                    - @inner ℝ X _ (P x - x) (P x - P y) := by linarith
    have hrw : @inner ℝ X _ (P y - y) (P x - P y) - @inner ℝ X _ (P x - x) (P x - P y)
             = @inner ℝ X _ ((P y - y) - (P x - x)) (P x - P y) := by
      rw [← inner_sub_left]
    rw [hrw] at hcombo
    have heq : ((P y - y) - (P x - x) : X) = (x - y) - (P x - P y) := by abel
    rw [heq, inner_sub_left] at hcombo
    linarith
  have hnorm : @inner ℝ X _ (P x - P y) (P x - P y) = ‖P x - P y‖^2 :=
    real_inner_self_eq_norm_sq (P x - P y)
  linarith [hkey, hnorm]

end Problems.proj_nonexpansive
