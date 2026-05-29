-- Compose two origin-fixing decompositions through `Equidecomp.trans`.
-- Witness finset is the pointwise product `S₂ ⋆ S₁` (`Finset.image₂ (·*·)`): on the
-- trans-source, `e₁` acts as some `g₁ ∈ S₁` and `e₂` (at `e₁ a`) as some `g₂ ∈ S₂`, so
-- the composite acts as `(g₂*g₁)•a` by `mul_smul`; each product fixes 0 since
-- `(g₂*g₁) 0 = g₂ (g₁ 0) = g₂ 0 = 0`. Direct leaf — no sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11516

namespace Problems.Geometry.banach_tarski

def decomp_trans_origin_fixing := @Problems.Geometry.banach_tarski.s11516

end Problems.Geometry.banach_tarski
