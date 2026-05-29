-- Lift the F₂ 2-paradoxical split through the free, fixed-point-free, M-invariant
-- action φ.  First take an orbit address (rep, wrd): every x∈M is x = φ(wrd x)•rep x
-- with the cocycle rep/wrd transform under the action (orbit_address_of_free_action).
-- The partition of F₂ by "first letter is generator 0?" pulls back to a partition of M:
--   f.source = words starting with letter 0 (a / a⁻¹), reconstructs M by id on a-words
--              and φ(of 0) on a⁻¹-words  (build_letter0_equidecomp);
--   g.source = the complement (empty word + b / b⁻¹ words), reconstructs M by id on
--              {1}∪b-words and φ(of 1) on b⁻¹-words  (build_non_letter0_equidecomp).
-- Combinator: obtain the address, build each piece, then disjointness/cover are the
-- trivial set algebra of {x∈M | P} ⊔ {x∈M | ¬P} = M.  Each sub-goal is strictly simpler:
-- the address drops all Equidecomp structure; each builder handles ONE generator only.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11464

namespace Problems.Geometry.banach_tarski

def paradoxical_of_free_isometry_action := @Problems.Geometry.banach_tarski.s11464

end Problems.Geometry.banach_tarski
