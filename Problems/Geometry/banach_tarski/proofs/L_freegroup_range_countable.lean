-- A monoid hom out of FreeGroup α has countable range whenever α is countable.
-- FreeGroup α inherits a Countable instance from α (it's a quotient of List (α × Bool)),
-- so Set.countable_range closes the goal directly — no sub-goals needed.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11418

namespace Problems.Geometry.banach_tarski

def freegroup_range_countable := @Problems.Geometry.banach_tarski.s11418

end Problems.Geometry.banach_tarski
