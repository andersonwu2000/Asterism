-- Take R := ψ (of 0), a single free generator of the proved SO(3) embedding ψ
-- (free_so3_embedding): an infinite-order det-1 rotation. For each n ≥ 1, R^n = ψ((of 0)^n)
-- with (of 0)^n ≠ 1, so R^n is a non-trivial det-1 isometry whose fixed set on the radius-1/2
-- sphere is finite (fixed_set_half_sphere_finite bridges rotation_fixed_set_on_sphere_finite
-- to radius 1/2). The union over n ≥ 1 of these fixed sets is countable, but the sphere is
-- uncountable (half_sphere_uncountable), so a point c with ‖c‖ = 1/2 escapes every power
-- (exists_not_fixed_in_uncountable_sphere). Sub-goals: of_pow_ne_one (generator has infinite
-- order), the radius-1/2 finiteness bridge, sphere uncountability, and the set-theoretic
-- "uncountable minus countably-many finite sets is nonempty" combine.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11514

namespace Problems.Geometry.banach_tarski

def exists_small_irrational_rotation := @Problems.Geometry.banach_tarski.s11514

end Problems.Geometry.banach_tarski
