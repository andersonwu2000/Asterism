import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem toword_ne_nil_of_ne_one (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    FreeGroup.toWord w ≠ [] := by simp_all only [ne_eq, FreeGroup.toWord_eq_nil_iff, not_false_eq_true]

end Problems.Geometry.banach_tarski
