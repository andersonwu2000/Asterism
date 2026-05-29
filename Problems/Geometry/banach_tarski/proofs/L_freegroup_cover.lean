import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- freegroup_cover: every FreeGroup element has empty toWord or a first letter (head?)
-- proof by ext + case split on whether toWord is [] or p::t
theorem freegroup_cover {α : Type*} [DecidableEq α] :
    {w : FreeGroup α | FreeGroup.toWord w = []}
      ∪ (⋃ p : α × Bool, {w : FreeGroup α | (FreeGroup.toWord w).head? = some p})
      = (Set.univ : Set (FreeGroup α)) := by
  ext w
  simp only [Set.mem_union, Set.mem_setOf_eq, Set.mem_iUnion, Set.mem_univ, iff_true]
  set L := FreeGroup.toWord w with hL
  rcases L with _ | ⟨p, t⟩
  · exact Or.inl rfl
  · exact Or.inr ⟨p, rfl⟩

end Problems.Geometry.banach_tarski