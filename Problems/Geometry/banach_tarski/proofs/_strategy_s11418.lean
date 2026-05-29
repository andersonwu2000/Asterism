import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- A monoid hom out of FreeGroup α has countable range whenever α is countable.
-- FreeGroup α inherits a Countable instance from α (it's a quotient of List (α × Bool)),
-- so Set.countable_range closes the goal directly — no sub-goals needed.
theorem s11418 {α : Type*} [Countable α] {H : Type*} [Group H]
    (φ : FreeGroup α →* H) :
    (Set.range (φ : FreeGroup α → H)).Countable  := by
  have : Countable (FreeGroup α) := inferInstance
  exact Set.countable_range _

end Problems.Geometry.banach_tarski
