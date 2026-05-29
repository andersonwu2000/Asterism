-- `lift f` is injective ⇔ trivial kernel; reduce to `lift f w = 1 → w = 1`.
-- `lift f w` equals the product over `toWord w` (representation lemma, via `lift_mk`),
-- so if `w ≠ 1` then `toWord w ≠ []` and the hypothesis `h` forbids that product = 1.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11411

namespace Problems.Geometry.banach_tarski

def freegroup_lift_injective_of_word_prod_ne_one := @Problems.Geometry.banach_tarski.s11411

end Problems.Geometry.banach_tarski
