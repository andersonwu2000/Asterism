import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_residue_step_first_a
import Problems.Geometry.banach_tarski.proofs.L_residue_step_first_ainv
import Problems.Geometry.banach_tarski.proofs.L_residue_step_first_b
import Problems.Geometry.banach_tarski.proofs.L_residue_step_first_binv

namespace Problems.Geometry.banach_tarski

-- Inductive step of the head-keyed mod-3 residue invariant, arithmetic half.
-- Split by the first letter `x` (4 generators); each generator is its own sub-goal:
--   residue_step_first_a / _ainv / _b / _binv — fixed-`x` instances where `foldr` reduces
--   to `step x (p,q,r)`, the inverse `hclass` branch is killed by `hhead`, and ¬3∣q' plus
--   the new residue relations follow by pure ℤ-mod-3 arithmetic.
-- Combinator: `fin_cases` on `x` dispatches to the matching fixed-letter lemma.
theorem s11405
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (x : Fin 2 × Bool) (M : List (Fin 2 × Bool))
    (hhead : M.head? ≠ some (x.1, !x.2))
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
  -- Case on the first letter `x = (x1, x2)`; `fin_cases x1 <;> cases x2` gives the four
  -- generators. Each branch is the inductive step for one fixed first letter: `foldr` over
  -- `x :: M` reduces to `step x (p,q,r)` via `hstep`, the new `head?` is `some x`, and the
  -- residue invariant propagates by pure ℤ-mod-3 arithmetic with the inverse branch of
  -- `hclass` pruned by `hhead`. Each sub-goal is strictly simpler: `x` is concrete, no
  -- FreeGroup content remains, only a 3-branch mod-3 case bash.
  obtain ⟨x1, x2⟩ := x
  fin_cases x1 <;> cases x2
  · exact residue_step_first_ainv step hstep M hhead p q r hfold hq hclass
  · exact residue_step_first_a step hstep M hhead p q r hfold hq hclass
  · exact residue_step_first_binv step hstep M hhead p q r hfold hq hclass
  · exact residue_step_first_b step hstep M hhead p q r hfold hq hclass

end Problems.Geometry.banach_tarski
