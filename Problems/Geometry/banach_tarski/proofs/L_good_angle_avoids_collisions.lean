-- Hilbert-hotel angle choice: ρ := R θ for a θ outside the countable "bad" set
-- B of angles causing a collision R(nθ)·p = q (n≥1, p,q ∈ D).
-- Sole sub-goal: B is countable [bad_angles_countable]. The "∃ θ ∉ B" step is
-- inlined (countable B ≠ univ since ℝ is uncountable) to dodge the dedupe-probe
-- leaf misfire. Combinator: take θ ∉ B, ρ := R θ; ρ0=0 by h0; disjointness is
-- exactly θ ∉ B via hpow.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11432

namespace Problems.Geometry.banach_tarski

def good_angle_avoids_collisions := @Problems.Geometry.banach_tarski.s11432

end Problems.Geometry.banach_tarski
