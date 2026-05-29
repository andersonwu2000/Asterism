import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_cons_head_ne_inv
import Problems.Geometry.banach_tarski.proofs.L_cons_residue_arith

namespace Problems.Geometry.banach_tarski

-- Prepend letter `x` to reduced nonempty tail `M`, carrying the head-keyed mod-3 residue
-- invariant from `M` to `x :: M`, via 2 strictly-simpler sub-goals.
--   `cons_head_ne_inv`     — FreeGroup combinatorics: a reduced `x :: M` cannot have `M`
--     start with `x`'s inverse `(x.1, !x.2)` (Red.Step.not cancellation + length).
--   `cons_residue_arith`   — pure ℤ/`Int.ModEq` core: with that head-inequality replacing
--     the FreeGroup reduce equation, `step x (p,q,r)` (= foldr over `x :: M`) satisfies the
--     head-keyed invariant; `hhead` + `hclass` + `¬3∣q` prune the residue state that would
--     make `3 ∣ q'`.
-- Combinator: derive `hhead` from reducedness, then hand the arithmetic the clean hypothesis.
theorem s11403
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
  -- Reducedness of `x :: M` forbids `M` from starting with `x`'s inverse.
  have hhead : M.head? ≠ some (x.1, !x.2) := cons_head_ne_inv x M hred hne
  -- Pure arithmetic core: with the FreeGroup reduce equation replaced by the clean
  -- head-inequality, `step x` carries the head-keyed mod-3 invariant to `x :: M`.
  exact cons_residue_arith step hstep x M hhead p q r hfold hq hclass



end Problems.Geometry.banach_tarski
