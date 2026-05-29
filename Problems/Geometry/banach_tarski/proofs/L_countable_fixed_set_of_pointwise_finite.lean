-- The fixed-point set in s is the union over nontrivial g of each g's fixed set.
-- {g | g ≠ 1} is countable (G countable); each fiber is finite (hfin) hence
-- countable; Set.Countable.biUnion closes it directly — no sub-goals needed.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11417

namespace Problems.Geometry.banach_tarski

def countable_fixed_set_of_pointwise_finite := @Problems.Geometry.banach_tarski.s11417

end Problems.Geometry.banach_tarski
