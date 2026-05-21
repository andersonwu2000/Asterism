import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_lift_translation_proj_eq_loop

namespace Problems.pi1_circle

-- Decompose by uniqueness of lifts (`IsCoveringMap.eq_liftPath_iff'`):
-- the candidate ContinuousMap `g(t) = Γ0(t) + r` (Γ0 = lift of γ' from 0)
-- projects to γ' via `Circle.exp_add` + `Circle.exp r = 1` and satisfies
-- `g 0 = r`, hence equals `liftPath γ' r hr` as continuous maps. Specialize
-- at t = 1 to read off `liftPath γ' r hr 1 = Γ0 1 + r = r + Γ0 1`. The single
-- sub-goal `lift_translation_proj_eq_loop` packages the projection identity
-- pointwise (uses `Circle.exp_add`, `liftPath_lifts`, and `γ'(0) = 1`).
theorem s10702
    (γ' : Path (1 : Circle) 1) (r : ℝ)
    (hr : γ'.toContinuousMap 0 = Circle.exp r) :
    Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap r hr 1
      = r + Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap 0
          (by simp : γ'.toContinuousMap 0 = Circle.exp 0) 1  := by
  have h_proj_pt := lift_translation_proj_eq_loop γ' r hr
  set Γ0 : C(unitInterval, ℝ) := Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap 0
      (by simp : γ'.toContinuousMap 0 = Circle.exp 0) with hΓ0_def
  let g : C(unitInterval, ℝ) := ⟨fun t => Γ0 t + r, by fun_prop⟩
  have h_proj : Circle.exp ∘ g = γ'.toContinuousMap := funext h_proj_pt
  have h_zero : g 0 = r := by
    change Γ0 0 + r = r
    rw [Circle.isCoveringMap_exp.liftPath_zero γ'.toContinuousMap 0
        (by simp : γ'.toContinuousMap 0 = Circle.exp 0)]
    ring
  have h_eq : g = Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap r hr :=
    (Circle.isCoveringMap_exp.eq_liftPath_iff' hr).mpr ⟨h_proj, h_zero⟩
  have h_eval : Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap r hr 1
      = Γ0 1 + r := by rw [← h_eq]; rfl
  linarith

end Problems.pi1_circle
