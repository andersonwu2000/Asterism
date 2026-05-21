import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_exists_loop_lift_endpoint

namespace Problems.pi1_circle

open Real

-- Surjectivity reduces to a single existence sub-goal: for every integer `n`
-- there is a loop `γ_n : Path (1:Circle) 1` whose lift evaluated at 1 equals
-- `n * (2π)`. Combined with `h_char` and cancellation by `2π ≠ 0`, this gives
-- `W' ⟦γ_n⟧ = n`. The existence sub-goal isolates the standard-loop
-- construction (e.g. `Circle.exp ∘ (t ↦ t * n * 2π)`), which is the only
-- non-trivial content remaining; the rest is bookkeeping.
theorem s10696
    (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ)
    (h_char : ∀ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (W' ⟦γ⟧ : ℝ) * (2 * π)) :
    Function.Surjective W'  := by
  intro n
  obtain ⟨γ, hγ⟩ := exists_loop_lift_endpoint W' h_char n
  refine ⟨⟦γ⟧, ?_⟩
  have key : (W' ⟦γ⟧ : ℝ) * (2 * π) = (n : ℝ) * (2 * π) := by
    rw [← h_char γ]; exact hγ
  exact_mod_cast mul_right_cancel₀ Real.two_pi_pos.ne' key

end Problems.pi1_circle

