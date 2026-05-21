import Mathlib
import Problems.pi1_circle.Defs

namespace Problems.pi1_circle

-- entry_kind: Builder
-- lift_translation_proj_eq_loop: liftPath_lifts + Circle.exp_add + exp r = 1 closes pointwise
-- projection identity. Uses Circle.exp_add to split exp(Γ0(t)+r), liftPath_lifts for
-- exp∘Γ0 = γ', and hr+γ'.source to derive Circle.exp r = 1.
theorem lift_translation_proj_eq_loop
    (γ' : Path (1 : Circle) 1) (r : ℝ)
    (hr : γ'.toContinuousMap 0 = Circle.exp r) :
    ∀ t : unitInterval,
      Circle.exp (Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap 0
          (by simp : γ'.toContinuousMap 0 = Circle.exp 0) t + r)
        = γ'.toContinuousMap t := by
  intro t
  have hpe : γ'.toContinuousMap 0 = Circle.exp 0 := by simp
  have hexp_r : Circle.exp r = 1 := by
    have h0 : γ'.toContinuousMap 0 = 1 := γ'.source
    rw [h0] at hr; exact hr.symm
  rw [Circle.exp_add]
  simp only [← Function.comp_apply (f := Circle.exp),
             Circle.isCoveringMap_exp.liftPath_lifts, hexp_r, mul_one]
end Problems.pi1_circle
