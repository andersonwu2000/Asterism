-- Membership = the upper-bound construction half. Build a rank-≤k truncation `S`
-- with ‖T−S‖ ≤ σ_k (`exists_truncation_norm_le_singularvalue`); the re-declared
-- lower-bound sub-goal gives σ_k ≤ ‖T−S‖ for that same S (`singularvalue_mem_lowerbounds`,
-- dedupe-aliases the lower-bound sibling), so antisymmetry pins ‖T−S‖ = σ_k.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11645

namespace Problems.LinearAlgebra.eckart_young

def eckart_young_membership := @Problems.LinearAlgebra.eckart_young.s11645

end Problems.LinearAlgebra.eckart_young
