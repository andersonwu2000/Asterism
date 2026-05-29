import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_integer_triple_core
import Problems.Geometry.banach_tarski.proofs.L_matrix_prod_realizes_triple

namespace Problems.Geometry.banach_tarski

-- swierczkowski_mod3_invariant: pure weakening of swierczkowski_integer_triple_core via
-- matrix_prod_realizes_triple — obtain (p,q,r) + ¬3∣q from the core invariant,
-- convert foldr to Matrix.mulVec via the bridge, drop the head-letter disjunction.
theorem swierczkowski_mod3_invariant
    (a aInv b bInv : Matrix (Fin 3) (Fin 3) ℝ)
    (ha : a = !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (haInv : aInv = !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hb : b = !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hbInv : bInv = !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (w : FreeGroup (Fin 2)) (hw : FreeGroup.toWord w ≠ []) :
    ∃ p q r : ℤ, ¬ (3 ∣ q) ∧
      Matrix.mulVec
        (((FreeGroup.toWord w).map
            (fun x : Fin 2 × Bool =>
              if x.1 = 0 then (if x.2 then a else aInv)
                         else (if x.2 then b else bInv))).prod)
        ![0, 1, 0]
      = ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2] := by
  let step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ :=
    fun x v =>
      if x.1 = 0 then
        if x.2 then (v.1 - 2 * v.2.1, 4 * v.1 + v.2.1, 3 * v.2.2)
               else (v.1 + 2 * v.2.1, -4 * v.1 + v.2.1, 3 * v.2.2)
      else
        if x.2 then (3 * v.1, v.2.1 - 4 * v.2.2, 2 * v.2.1 + v.2.2)
               else (3 * v.1, v.2.1 + 4 * v.2.2, -2 * v.2.1 + v.2.2)
  have hstep : ∀ p q r : ℤ,
      step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
      step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
      step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
      step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r) := by
    intro p q r; refine ⟨?_, ?_, ?_, ?_⟩ <;> simp [step]
  obtain ⟨p, q, r, hfold, hndvd⟩ :=
    swierczkowski_integer_triple_core step hstep w hw
  exact ⟨p, q, r, hndvd,
    matrix_prod_realizes_triple a aInv b bInv ha haInv hb hbInv step hstep w p q r hfold⟩

end Problems.Geometry.banach_tarski
