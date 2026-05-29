-- Origin-fixing mirror of s11464: lift the F₂ 2-paradoxical split through φ, now ALSO

-- exposing the realizing Finsets Sf,Sg with every element fixing 0.  Orbit address
-- (rep,wrd) is cited inline from the proved orbit_address_of_free_action; the partition
-- of M by "first letter = generator 0?" pulls back to f.source/g.source.  Two new
-- origin-fixing builders reconstruct each piece together with its origin-fixing Finset
-- (letter-0 piece: Sf={1,φ(of 0)}; complement: Hilbert-hotel φ(of 1)-tower).
-- Combinator: disjointness + cover are the same {x∈M|P} ⊔ {x∈M|¬P} = M set algebra as
-- s11464; the IsDecompOn + origin-fixing fields thread straight through from the builders.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11515

namespace Problems.Geometry.banach_tarski

def paradoxical_of_free_isometry_action_origin_fixing := @Problems.Geometry.banach_tarski.s11515

end Problems.Geometry.banach_tarski
