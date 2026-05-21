import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_int_mul_two_pi_inj
import Problems.pi1_circle.proofs.L_lift_endpoint_trans_eq_add

namespace Problems.pi1_circle

open Real

-- Reduce ℤ-additivity of W' on γ.trans γ' to ℝ-additivity of the lifted
-- endpoints (single sub-goal `lift_endpoint_trans_eq_add`); h_char then
-- converts both sides to ℝ scalar form and int_mul_two_pi_inj finishes.
theorem s10694
    (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ)
    (h_char : ∀ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (W' ⟦γ⟧ : ℝ) * (2 * π)) :
    ∀ (γ γ' : Path (1 : Circle) 1),
      W' (⟦γ.trans γ'⟧ : Path.Homotopic.Quotient (1 : Circle) 1)
        = W' (⟦γ⟧ : Path.Homotopic.Quotient (1 : Circle) 1)
          + W' (⟦γ'⟧ : Path.Homotopic.Quotient (1 : Circle) 1)  := by
  intro γ γ'
  have h_trans := lift_endpoint_trans_eq_add γ γ'
  have hγγ' := h_char (γ.trans γ')
  have hγ := h_char γ
  have hγ' := h_char γ'
  apply int_mul_two_pi_inj
  push_cast
  linarith [h_trans, hγγ', hγ, hγ']

end Problems.pi1_circle
