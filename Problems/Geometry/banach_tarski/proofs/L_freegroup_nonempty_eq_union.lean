import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- freegroup_nonempty_eq_union: non-identity FreeGroup elements are exactly those
-- whose reduced word has some head letter (α × Bool); pure List.head? ↔ non-nil duality.
theorem freegroup_nonempty_eq_union {α : Type*} [DecidableEq α] :
    {w : FreeGroup α | FreeGroup.toWord w = []}ᶜ
        = ⋃ p : α × Bool, {w : FreeGroup α | (FreeGroup.toWord w).head? = some p} := by
  ext w
  simp only [Set.mem_compl_iff, Set.mem_setOf_eq, Set.mem_iUnion]
  constructor
  · intro h
    obtain ⟨hd, tl, htl⟩ := List.exists_cons_of_ne_nil h
    exact ⟨hd, by rw [htl]; rfl⟩
  · rintro ⟨p, hp⟩
    intro heq
    simp [heq] at hp

end Problems.Geometry.banach_tarski
