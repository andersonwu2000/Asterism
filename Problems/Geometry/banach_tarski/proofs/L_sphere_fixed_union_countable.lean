import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- sphere_fixed_union_countable: countable union of finite fixed-point fibers
-- FreeGroup (Fin 2) is countable; each fiber {x | φ w x = x} is finite by hfin.
theorem sphere_fixed_union_countable
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfin : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite) :
    (⋃ (w : FreeGroup (Fin 2)) (_ : w ≠ 1),
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}).Countable := by
  apply Set.countable_iUnion
  intro w
  by_cases hw : w = 1
  · simp [hw]
  · exact (hfin w hw).countable.mono (Set.iUnion_subset fun _ => subset_refl _)

end Problems.Geometry.banach_tarski
