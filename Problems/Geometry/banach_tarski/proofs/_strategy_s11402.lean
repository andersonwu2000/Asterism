import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_head_ne_inv_of_reduced
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_residue_step_arith

namespace Problems.Geometry.banach_tarski

-- Inductive step of the head-keyed mod-3 residue invariant: split FreeGroup reducedness
-- from pure arithmetic.
--   `head_ne_inv_of_reduced`  — reducedness of `x :: M` forbids `M` from starting with `x`'s
--     inverse `(x.1, !x.2)`; the only FreeGroup content here.
--   `swierczkowski_residue_step_arith` — with that clean head constraint (no FreeGroup left),
--     `foldr step (0,1,0) (x::M) = step x (p,q,r)`; case on `x`, prune the forbidden
--     second-letter residue state via `hhead`, and propagate the invariant by mod-3 arithmetic.
-- Combinator: derive `hhead`, feed both sub-goals together. Each is strictly simpler — one is
-- pure list/FreeGroup, the other pure ℤ-mod-3 with reducedness pre-resolved.
theorem s11402
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (x : Fin 2 × Bool) (M : List (Fin 2 × Bool))
    (hred : FreeGroup.reduce (x :: M) = x :: M) (hne : M ≠ [])
    (p q r : ℤ) (hfold : List.foldr step (0, 1, 0) M = (p, q, r)) (hq : ¬ (3 ∣ q))
    (hclass :
      (M.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3])) :
    ∃ p' q' r' : ℤ,
      List.foldr step (0, 1, 0) (x :: M) = (p', q', r') ∧ ¬ (3 ∣ q') ∧
      ( ((x :: M).head? = some (0, true)  ∧ p' ≡ q'  [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        ((x :: M).head? = some (0, false) ∧ p' ≡ -q' [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        ((x :: M).head? = some (1, true)  ∧ q' ≡ -r' [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ∨
        ((x :: M).head? = some (1, false) ∧ q' ≡ r'  [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) )  := by
  have hhead : M.head? ≠ some (x.1, !x.2) := head_ne_inv_of_reduced x M hred
  exact swierczkowski_residue_step_arith step hstep x M hhead p q r hfold hq hclass

end Problems.Geometry.banach_tarski
