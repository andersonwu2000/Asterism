import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem b_letter_pieces_disjoint (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    Disjoint {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)}
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)} := by grind

end Problems.Geometry.banach_tarski
