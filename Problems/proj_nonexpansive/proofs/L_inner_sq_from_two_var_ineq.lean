-- inner_sq_from_two_var_ineq: Closes by expanding `inner (c - d) (a - b)` via the abelian group identity `c - d = (c - a) + (a - b) + (b - d)` (proved with `abel`) and bilinearity (`inner_add_left` twice), then rewriting `inner (c - a) (a - b) = inner (a - c) (b - a)` via `inner_neg_left`/`inner_neg_right`, substituting `inner (a - b) (a - b) = ‖a - b‖^2` via `real_inner_self_eq_norm_sq`, and letting `linarith` combine these equations with the two non-negativity hypotheses.
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem inner_sq_from_two_var_ineq {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b c d : X) :
    @inner ℝ _ _ (a - c) (b - a) ≥ 0 →
    @inner ℝ _ _ (b - d) (a - b) ≥ 0 →
    ‖a - b‖ ^ 2 ≤ @inner ℝ _ _ (c - d) (a - b) := by
  intro h1 h2
  have step1 : @inner ℝ _ _ (c - d) (a - b) =
      @inner ℝ _ _ (c - a) (a - b) + @inner ℝ _ _ (a - b) (a - b) + @inner ℝ _ _ (b - d) (a - b) := by
    have factored : (c : X) - d = (c - a) + (a - b) + (b - d) := by abel
    rw [factored, inner_add_left, inner_add_left]
  have step2 : @inner ℝ _ _ (c - a) (a - b) = @inner ℝ _ _ (a - c) (b - a) := by
    have h3 : (c : X) - a = -(a - c) := by abel
    have h4 : (a : X) - b = -(b - a) := by abel
    rw [h3, h4, inner_neg_left, inner_neg_right, neg_neg]
  have step3 : @inner ℝ _ _ (a - b) (a - b) = ‖a - b‖ ^ 2 := real_inner_self_eq_norm_sq (a - b)
  linarith [step1, step2, step3]

end Problems.proj_nonexpansive
