import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem letter0_pieces_disjoint (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    Disjoint {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} := by grind

end Problems.Geometry.banach_tarski