-- S realizes the cone map: each cone point y = r•x (r∈(0,1], x∈e.source⊆sphere) has ‖y‖=r,
-- ‖y‖⁻¹•y = x, so f y = r • e x = r • (g•x) for the g∈S realizing e at x; since g fixes 0 it is
-- ℝ-linear (s11475), so g•(r•x) = r•(g•x), matching. Leaf: cite s11475 + norm algebra inline.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11512

namespace Problems.Geometry.banach_tarski

def cone_is_decomp := @Problems.Geometry.banach_tarski.s11512

end Problems.Geometry.banach_tarski
