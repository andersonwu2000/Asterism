import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_cons_residue_step
import Problems.Geometry.banach_tarski.proofs.L_single_letter_residue_base
import Problems.Geometry.banach_tarski.proofs.L_tail_of_reduced_is_reduced

namespace Problems.Geometry.banach_tarski

-- Strip the FreeGroup wrapper and induct on the reduced word `L` from its leftmost
-- letter (the head, which `foldr` applies outermost), into 3 strictly-simpler sub-goals.
--   `single_letter_residue_base`   — single-letter words `[x]` satisfy the head-keyed
--     mod-3 residue invariant (a direct computation of `step x (0,1,0)` over 4 letters).
--   `tail_of_reduced_is_reduced`   — the tail of a reduced word is reduced, firing the IH.
--   `cons_residue_step`            — prepending a letter `x` to a reduced nonempty tail
--     whose head-keyed invariant holds yields the invariant for `x :: tail`, using
--     reducedness to prune impossible second-letter residue states.
-- Combinator is `induction L`: `nil` contradicts `hne`; the single-letter `cons … nil`
-- case is the base lemma; `cons … cons` threads the IH (on the reduced nonempty tail)
-- through the step lemma.  The sub-goals emit the conjuncts foldr-first, so each branch
-- re-associates `⟨…⟩` into this goal's `¬3∣q ∧ disj ∧ foldr` order.
theorem s11400
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (L : List (Fin 2 × Bool)) (hred : FreeGroup.reduce L = L) (hne : L ≠ []) :
    ∃ p q r : ℤ,
      ¬ (3 ∣ q) ∧
      ( (L.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ) ∧
      List.foldr step (0, 1, 0) L = (p, q, r)  := by
  revert hred hne
  induction L with
  | nil => intro _ hne; exact absurd rfl hne
  | cons x tl ih =>
    intro hred hne
    cases tl with
    | nil =>
      obtain ⟨p, q, r, hfold, hq, hclass⟩ := single_letter_residue_base step hstep x
      exact ⟨p, q, r, hq, hclass, hfold⟩
    | cons y tl' =>
      have htl_ne : (y :: tl') ≠ [] := by simp
      have htl_red := tail_of_reduced_is_reduced x (y :: tl') hred
      obtain ⟨p, q, r, hq, hclass, hfold⟩ := ih htl_red htl_ne
      obtain ⟨p', q', r', hfold', hq', hclass'⟩ :=
        cons_residue_step step hstep x (y :: tl') hred htl_ne p q r hfold hq hclass
      exact ⟨p', q', r', hq', hclass', hfold'⟩

end Problems.Geometry.banach_tarski
