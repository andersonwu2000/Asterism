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
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11400

namespace Problems.Geometry.banach_tarski

def residue_invariant_foldr_list := @Problems.Geometry.banach_tarski.s11400

end Problems.Geometry.banach_tarski
