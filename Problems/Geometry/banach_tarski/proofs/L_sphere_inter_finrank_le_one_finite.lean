-- Direct (leaf) proof: finrank ℝ W ≤ 1 ⇒ via `finrank_le_one_iff` every x ∈ W is c • v
-- for a fixed v. A unit-norm c • v forces ‖c‖ * ‖v‖ = 1, i.e. c = ±‖v‖⁻¹, so the
-- sphere∩W set is contained in the 2-point set {‖v‖⁻¹ • v, -‖v‖⁻¹ • v}, hence finite.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11420

namespace Problems.Geometry.banach_tarski

def sphere_inter_finrank_le_one_finite := @Problems.Geometry.banach_tarski.s11420

end Problems.Geometry.banach_tarski
