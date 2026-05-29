-- Mazur–Ulam: a 0-fixing isometry equivalence of a real normed space is ℝ-linear.
-- Promote `g` to the linear isometry equivalence `L := g.toRealLinearIsometryEquivOfMapZero hg`,
-- whose `map_smul` gives `L (r•x) = r • L x`; rewrite `⇑L = ⇑g` via the coe lemma. Direct, no sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11475

namespace Problems.Geometry.banach_tarski

def isometry_fixing_origin_smul_comm := @Problems.Geometry.banach_tarski.s11475

end Problems.Geometry.banach_tarski
