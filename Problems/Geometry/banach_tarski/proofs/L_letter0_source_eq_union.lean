import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem letter0_source_eq_union (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}
      = {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}
        ∪ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} := by aesop

end Problems.Geometry.banach_tarski