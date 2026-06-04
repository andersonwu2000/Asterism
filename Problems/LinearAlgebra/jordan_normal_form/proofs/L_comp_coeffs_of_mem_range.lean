-- Direct leaf proof: complement coeffs vanish from `hmem` + disjointness + cb's LI.
-- The block `∑ c, g⟨inr c,0⟩ • cb c` lies in C (each cb c ∈ C); `hmem` puts it in `range N`;
-- `hC2`-disjointness collapses C ⊓ range N to ⊥, so the block = 0; then `cb.linearIndependent`
-- (pushed along the injective subtype) + `Fintype.linearIndependent_iff` kills every coeff.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11033

namespace Problems.LinearAlgebra.jordan_normal_form

def comp_coeffs_of_mem_range := @Problems.LinearAlgebra.jordan_normal_form.s11033

end Problems.LinearAlgebra.jordan_normal_form
