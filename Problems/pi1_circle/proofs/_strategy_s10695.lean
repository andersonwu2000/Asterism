import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_lift_endpoint_eq_imp_quot_eq

namespace Problems.pi1_circle

-- Reduce `Function.Injective W'` to a single covering-space lemma:
-- after `Quotient.ind` exposes loop representatives `γa, γb`, the chain
-- `W' ⟦γa⟧ = W' ⟦γb⟧ → (W' ⟦γa⟧ : ℝ) * (2π) = (W' ⟦γb⟧ : ℝ) * (2π)
--  → Γa(1) = Γb(1)` (via `h_char`) leaves only `lift_endpoint_eq_imp_quot_eq`
-- (converse of `lift_endpoint_eq_of_homotopic`) to finish. That sub-goal
-- holds because the universal cover ℝ → Circle has simply-connected total
-- space, so equal lifted endpoints give a homotopy in ℝ that pushes down.
theorem s10695
    (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ)
    (h_char : ∀ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (W' ⟦γ⟧ : ℝ) * (2 * π)) :
    Function.Injective W'  := by
  intro a b hab
  induction a using Quotient.ind with | _ γa =>
  induction b using Quotient.ind with | _ γb =>
  have h_lift_eq :
      Circle.isCoveringMap_exp.liftPath γa.toContinuousMap 0
          (by simp : γa.toContinuousMap 0 = Circle.exp 0) 1
        = Circle.isCoveringMap_exp.liftPath γb.toContinuousMap 0
          (by simp : γb.toContinuousMap 0 = Circle.exp 0) 1 := by
    rw [h_char γa, h_char γb, hab]
  have h_sub : (⟦γa⟧ : Path.Homotopic.Quotient (1 : Circle) 1) = ⟦γb⟧ :=
    lift_endpoint_eq_imp_quot_eq γa γb h_lift_eq
  exact h_sub

end Problems.pi1_circle
