import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_freegroup_nonempty_eq_union
import Problems.Geometry.banach_tarski.proofs.L_freegroup_starts_disjoint

namespace Problems.Geometry.banach_tarski

-- Split the conjunction into its two independent conjuncts.
-- h_disj: distinct head-letters give disjoint word-sets (head? is functional).
-- h_cover: non-empty words are exactly those with some head-letter (head? = some p).
-- Each conjunct stands alone and is strictly simpler than the pair; combine with And.intro.
theorem s11387 {α : Type*} [DecidableEq α] :
    (∀ p q : α × Bool, p ≠ q →
        Disjoint {w : FreeGroup α | (FreeGroup.toWord w).head? = some p}
                 {w : FreeGroup α | (FreeGroup.toWord w).head? = some q})
    ∧ {w : FreeGroup α | FreeGroup.toWord w = []}ᶜ
        = ⋃ p : α × Bool, {w : FreeGroup α | (FreeGroup.toWord w).head? = some p}  := by
  have h_disj := freegroup_starts_disjoint (α := α)
  have h_cover := freegroup_nonempty_eq_union (α := α)
  exact ⟨h_disj, h_cover⟩

end Problems.Geometry.banach_tarski
