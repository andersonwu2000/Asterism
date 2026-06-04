-- Direct conjugation transfer of a fixed point across `φ : S ≃ₜ T`.
-- Set `h := φ ∘ g ∘ φ.symm : T → T`; continuity is `fun_prop` from `hg`,
-- `φ.continuous`, `φ.symm.continuous`. Brouwer on T gives `y` with `h y = y`;
-- applying `φ.symm` to both sides yields `g (φ.symm y) = φ.symm y`.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10830

namespace Problems.Topology.brouwer_fixed_point

def fixed_point_subtype_via_homeo := @Problems.Topology.brouwer_fixed_point.s10830

end Problems.Topology.brouwer_fixed_point
