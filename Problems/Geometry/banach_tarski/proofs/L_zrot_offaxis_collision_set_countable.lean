-- Off-axis collision set {t | R0 t p = q} is countable, via a cosine level set.
-- For off-axis p the rotation angle's cosine is pinned: R0 t p = q forces
-- cos t = (p₀q₀ + p₁q₁)/(p₀²+p₁²), a single fixed value (collision_forces_cos:
-- unfold the rotation matrix on components 0,1 and solve the 2×2 system).
-- A cosine level set {t | cos t = c} is countable (cos_level_set_countable:
-- cos is strictly monotone on each [kπ,(k+1)π], so ≤1 root per interval over a
-- countable cover). The collision set is a subset of it, so Set.Countable.mono
-- transports countability back. Both sub-goals are strictly simpler: one is pure
-- matrix algebra, the other a matrix-free analytic fact.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11460

namespace Problems.Geometry.banach_tarski

def zrot_offaxis_collision_set_countable := @Problems.Geometry.banach_tarski.s11460

end Problems.Geometry.banach_tarski
