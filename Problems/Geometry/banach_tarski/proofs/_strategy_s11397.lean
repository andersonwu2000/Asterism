import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_residue_list

namespace Problems.Geometry.banach_tarski

-- Generalize to a statement about an arbitrary REDUCED letter-list, then induct from the
-- leftmost letter (the head, which `foldr` applies outermost). The single sub-goal
-- `swierczkowski_residue_list` restates the head-keyed residue disjunction over a plain
-- `List (Fin 2 × Bool)` with explicit reducedness `FreeGroup.reduce L = L` — stripping the
-- FreeGroup wrapper so structural `induction L` is directly available and the residue IH
-- closes. Here we just instantiate it at `L := toWord w`, which is reduced
-- (`FreeGroup.reduce_toWord`) and nonempty (`hw`); the combinator is a direct `exact`.
theorem s11397
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (w : FreeGroup (Fin 2)) (hw : FreeGroup.toWord w ≠ []) :
    ∃ p q r : ℤ,
      List.foldr step (0, 1, 0) (FreeGroup.toWord w) = (p, q, r) ∧
      ¬ (3 ∣ q) ∧
      ( ((FreeGroup.toWord w).head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ((FreeGroup.toWord w).head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ((FreeGroup.toWord w).head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        ((FreeGroup.toWord w).head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) )  := by
  exact swierczkowski_residue_list step hstep
    (FreeGroup.toWord w) (FreeGroup.reduce_toWord w) hw



end Problems.Geometry.banach_tarski
