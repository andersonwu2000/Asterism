import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_reduce_cons_tail_reduced
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_residue_base
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_residue_step

namespace Problems.Geometry.banach_tarski

-- Strip the FreeGroup wrapper and induct on the reduced word `L` from its leftmost letter
-- (the head, which `foldr` applies outermost), decomposing into 3 strictly-simpler sub-goals.
--   `swierczkowski_residue_base`  — single-letter words `[x]` satisfy the head-keyed mod-3
--     residue invariant (a direct computation of `step x (0,1,0)` over the 4 letters).
--   `reduce_cons_tail_reduced`    — the tail of a reduced word is reduced, so the IH fires.
--   `swierczkowski_residue_step`  — the inductive step: prepending a letter `x` to a reduced
--     nonempty tail whose (head-keyed) invariant holds yields the invariant for `x :: tail`,
--     using reducedness of `x :: tail` to prune impossible second-letter residue states (the
--     corrected full `(p,q,r) mod 3` invariant).
-- Combinator: `induction L`. The `nil` case contradicts `hL`; the single-letter `cons … nil`
-- case closes by the base lemma; the `cons … cons` case threads the IH (on the reduced
-- nonempty tail) through the step lemma. Each sub-goal is strictly smaller than the parent.
theorem s11398
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (L : List (Fin 2 × Bool)) (hred : FreeGroup.reduce L = L) (hL : L ≠ []) :
    ∃ p q r : ℤ,
      List.foldr step (0, 1, 0) L = (p, q, r) ∧
      ¬ (3 ∣ q) ∧
      ( (L.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) )  := by
  revert hred hL
  induction L with
  | nil => intro _ hL; exact absurd rfl hL
  | cons x tl ih =>
    intro hred hL
    cases tl with
    | nil => exact swierczkowski_residue_base step hstep x
    | cons y tl' =>
      have htl_ne : (y :: tl') ≠ [] := by simp
      have htl_red := reduce_cons_tail_reduced x (y :: tl') hred
      obtain ⟨p, q, r, hfold, hq, hclass⟩ := ih htl_red htl_ne
      exact swierczkowski_residue_step step hstep x (y :: tl') hred htl_ne p q r hfold hq hclass

end Problems.Geometry.banach_tarski
