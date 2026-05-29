-- Hilbert-hotel z-axis angle choice (z-axis analogue of good_angle_avoids_collisions / s11432).
-- Sole brick: the "bad" set B = {θ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0} is countable
-- [proved sibling zaxis_bad_angles_countable]. The "∃ θ ∉ B" step is inlined (countable B ≠ univ
-- since ℝ is uncountable). Combinator: take θ ∉ B; for p ∈ D, landing on the z-axis would witness
-- membership in B, contradiction.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11453

namespace Problems.Geometry.banach_tarski

def good_angle_avoids_zaxis := @Problems.Geometry.banach_tarski.s11453

end Problems.Geometry.banach_tarski
