import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem freegroup_starts_disjoint {α : Type*} [DecidableEq α] :
    ∀ p q : α × Bool, p ≠ q →
        Disjoint {w : FreeGroup α | (FreeGroup.toWord w).head? = some p}
                 {w : FreeGroup α | (FreeGroup.toWord w).head? = some q} := by grind

end Problems.Geometry.banach_tarski
