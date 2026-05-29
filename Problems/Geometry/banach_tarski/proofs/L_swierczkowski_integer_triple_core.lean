import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_residue_invariant_foldr_list

namespace Problems.Geometry.banach_tarski

-- swierczkowski_integer_triple_core: cite residue_invariant_foldr_list (s11400) and drop the
-- head-letter disjunction; reassociate to this goal's (foldr = … ∧ ¬3∣q) order.
theorem swierczkowski_integer_triple_core
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (w : FreeGroup (Fin 2)) (hw : FreeGroup.toWord w ≠ []) :
    ∃ p q r : ℤ,
      List.foldr step (0, 1, 0) (FreeGroup.toWord w) = (p, q, r) ∧ ¬ (3 : ℤ) ∣ q := by
  obtain ⟨p, q, r, hq, _hdisj, hfold⟩ :=
    residue_invariant_foldr_list step hstep (FreeGroup.toWord w)
      (FreeGroup.reduce_toWord w) hw
  exact ⟨p, q, r, hfold, hq⟩

end Problems.Geometry.banach_tarski

