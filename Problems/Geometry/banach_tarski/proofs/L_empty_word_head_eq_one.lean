import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem empty_word_head_eq_one : ∀ (w : FreeGroup (Fin 2)),
    (FreeGroup.toWord w).head? = none → w = 1 := by norm_num

end Problems.Geometry.banach_tarski
