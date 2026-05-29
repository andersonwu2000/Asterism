-- Direct leaf: conjugation transports the disjoint orbit.
-- (g⁻¹·ρ₀·g)^n = g⁻¹·ρ₀ⁿ·g (conj_pow), so its image of D is g⁻¹ '' (ρ₀ⁿ '' (g '' D));
-- disjointness then transfers across the injective map g⁻¹ via Set.disjoint_image_iff,
-- reducing each pair to the hypothesis h on the ρ₀-orbit of g '' D.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11456

namespace Problems.Geometry.banach_tarski

def conj_pairwise_transport := @Problems.Geometry.banach_tarski.s11456

end Problems.Geometry.banach_tarski
