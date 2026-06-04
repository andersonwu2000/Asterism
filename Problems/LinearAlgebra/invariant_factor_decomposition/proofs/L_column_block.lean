-- Direct construction (was: circular `pad_and_place`). Only the sorting is delegated.
--   `sorted_enum` (sub-goal): enumerate J in weight-monotone order, `e : Fin #J ≃ J`
--     with `w ∘ e` monotone — strictly smaller (no Fin-r / placement structure).
-- patch builds the witnesses explicitly: place j at `r - #J + e.symm j` (bottom block),
-- pad positions below `r - #J` with 0.  Monotone: padding 0 ≤ sorted tail, tail monotone
-- via `he`.  The five conjuncts are then Fin/Nat bookkeeping (omega + e.apply_symm_apply).
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11588

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def column_block := @Problems.LinearAlgebra.invariant_factor_decomposition.s11588

end Problems.LinearAlgebra.invariant_factor_decomposition
