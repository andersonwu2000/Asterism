-- Direct list induction: each factor f x = c • g x contributes one c, so the
-- whole product scales by c^len. cons step uses smul_mul_smul_comm to merge the
-- two scalars and pow_succ' (c^(n+1) = c * c^n) to match the accumulated power.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11410

namespace Problems.Geometry.banach_tarski

def map_prod_eq_pow_smul := @Problems.Geometry.banach_tarski.s11410

end Problems.Geometry.banach_tarski
