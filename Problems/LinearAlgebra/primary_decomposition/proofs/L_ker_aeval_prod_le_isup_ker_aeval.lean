-- Direct induction on n (no sub-goals; leaf-bypass).
-- Peel q 0 off the product via `Fin.prod_univ_succ`; q 0 is coprime to the tail
-- ∏ q i.succ (pairwise coprimality + `IsCoprime.prod_right`), so the 2-factor
-- `Polynomial.sup_ker_aeval_eq_ker_aeval_mul_of_coprime` splits the kernel into
-- ker(aeval T (q 0)) ⊔ ker(aeval T (tail)); the IH bounds the tail kernel.
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11560

namespace Problems.LinearAlgebra.primary_decomposition

def ker_aeval_prod_le_isup_ker_aeval := @Problems.LinearAlgebra.primary_decomposition.s11560

end Problems.LinearAlgebra.primary_decomposition
