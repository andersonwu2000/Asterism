-- Reduce `lift g w ≠ 1` to injectivity of `lift g`: sibling
-- `freegroup_lift_injective_of_word_prod_ne_one` (s11411) gives `Injective (lift g)` from a
-- per-word G-product-≠-1 hypothesis, so `lift g w = 1 = lift g 1` would force `w = 1`.
-- The one sub-goal `gen_word_prod_ne_one` transports `hword`'s matrix-product fact to the
-- needed G-product fact through the injective monoid hom `mat`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11486

namespace Problems.Geometry.banach_tarski

def lift_ne_one := @Problems.Geometry.banach_tarski.s11486

end Problems.Geometry.banach_tarski
