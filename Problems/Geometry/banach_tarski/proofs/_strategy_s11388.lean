import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_starts_disjoint
import Problems.Geometry.banach_tarski.proofs.L_translate_starts_eq_compl

namespace Problems.Geometry.banach_tarski

open scoped Pointwise

-- Direct assembly of the F₂ paradoxical-decomposition data from two sub-goals.
-- Conjunct 1 (PairwiseDisjoint over the 4 head-letters): each pair reduces to
--   `starts_disjoint` (distinct head? ⇒ disjoint word-sets).
-- Conjuncts 2,3 (translate-covers): `translate_starts_eq_compl i/j` rewrites
--   `of x • W_{x,false}` to `(W_{x,true})ᶜ`, then `Set.union_compl_self` closes `S ∪ Sᶜ = univ`.
theorem s11388 {α : Type*} [DecidableEq α] (i j : α) (hij : i ≠ j) :
    ({(i, true), (i, false), (j, true), (j, false)} : Set (α × Bool)).PairwiseDisjoint
        (fun p => {w : FreeGroup α | (FreeGroup.toWord w).head? = some p})
      ∧ {w : FreeGroup α | (FreeGroup.toWord w).head? = some (i, true)}
          ∪ FreeGroup.of i • {w : FreeGroup α | (FreeGroup.toWord w).head? = some (i, false)}
        = Set.univ
      ∧ {w : FreeGroup α | (FreeGroup.toWord w).head? = some (j, true)}
          ∪ FreeGroup.of j • {w : FreeGroup α | (FreeGroup.toWord w).head? = some (j, false)}
        = Set.univ  := by
  have h_disj := starts_disjoint (α := α)
  have h_tr_i := translate_starts_eq_compl i
  have h_tr_j := translate_starts_eq_compl j
  refine ⟨?_, ?_, ?_⟩
  · intro x _ y _ hxy
    exact h_disj x y hxy
  · rw [h_tr_i]; exact Set.union_compl_self _
  · rw [h_tr_j]; exact Set.union_compl_self _

end Problems.Geometry.banach_tarski
