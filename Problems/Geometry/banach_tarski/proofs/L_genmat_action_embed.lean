import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- genmat_action_embed: matrix mulVec on embedded integer triple realizes the step function
-- Case-split on all 4 generators; substitute concrete matrix; rewrite step via hstep;
-- close each component with ring after ring_nf + simp [√2^2=2].
theorem genmat_action_embed
    (a aInv b bInv : Matrix (Fin 3) (Fin 3) ℝ)
    (ha : a = !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (haInv : aInv = !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hb : b = !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hbInv : bInv = !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r)) :
    ∀ (x : Fin 2 × Bool) (v : ℤ × ℤ × ℤ),
      Matrix.mulVec
        (if x.1 = 0 then (if x.2 then a else aInv) else (if x.2 then b else bInv))
        ![(v.1 : ℝ) * Real.sqrt 2, (v.2.1 : ℝ), (v.2.2 : ℝ) * Real.sqrt 2]
      = ![((step x v).1 : ℝ) * Real.sqrt 2, ((step x v).2.1 : ℝ),
          ((step x v).2.2 : ℝ) * Real.sqrt 2] := by
  intro x v
  obtain ⟨p, q, r⟩ := v
  obtain ⟨xi, xb⟩ := x
  have hpow : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have h := hstep p q r
  obtain ⟨h0t, h0f, h1t, h1f⟩ := h
  subst ha haInv hb hbInv
  fin_cases xi <;> fin_cases xb <;>
  simp only [Fin.zero_eta, Fin.isValue, Fin.mk_one, Fin.reduceEq, Bool.false_eq_true,
             ite_false, ite_true] <;>
  simp only [h0t, h0f, h1t, h1f] <;>
  funext i <;> fin_cases i <;>
  simp only [Matrix.mulVec, Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.head_cons,
             Matrix.head_fin_const, Fin.isValue, Matrix.of_apply,
             Finset.sum_fin_eq_sum_range] <;>
  simp [Fin.sum_univ_three, Matrix.cons_val_zero, Matrix.cons_val_one,
        Matrix.head_cons] <;>
  push_cast <;>
  ring_nf <;>
  simp only [hpow] <;>
  ring

end Problems.Geometry.banach_tarski
