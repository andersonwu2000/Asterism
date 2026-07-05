-- Boundary-centered clone of s11997: identical PoU-weighted calc, but the covering
-- comes from `exists_boundary_centered_bump_covering` (interior-centered bumps stay
-- interior, via hDich) so the per-chart leg can case-split center ∈ ∂M vs interior.
-- The per-i leg `bump_stokes_per_chart_centered` carries the per-i specialization
-- `hDich i` (matching the existing open goal seeded by s17648 so the cite links
-- rather than re-inserts); the four finsum/additivity legs are covering-generic
-- proved Library lemmas, cited unchanged.
import Mathlib
import Problems.Geometry.stokes_theorem.Defs
import Problems.Geometry.stokes_theorem.proofs._strategy_s17649

namespace Problems.Geometry.stokes_theorem

def main := @Problems.Geometry.stokes_theorem.s17649

end Problems.Geometry.stokes_theorem
