-- Direct leaf computation: each of the 4 generator matrices acting on the
-- integer-lattice vector (p√2, q, r√2) yields the claimed integer recursion.
-- Split the conjunction, then per matrix entry: unfold mulVec, ring_nf to
-- collect the lone √2² term, rewrite √2²=2 (hpow), close by ring. No
-- sub-goals — leaf-bypass.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11392

namespace Problems.Geometry.banach_tarski

def rotation_generators_integer_recursion := @Problems.Geometry.banach_tarski.s11392

end Problems.Geometry.banach_tarski
