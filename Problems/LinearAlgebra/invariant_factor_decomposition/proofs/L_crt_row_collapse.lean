import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_crt_directsum_prod_quot

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- entry_kind: Backward
theorem crt_row_collapse {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    Nonempty ((DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {g i}))
      ≃ₗ[Polynomial K] (Polynomial K ⧸ Submodule.span (Polynomial K) {∏ i, g i})) := by apply crt_directsum_prod_quot <;> assumption

end Problems.LinearAlgebra.invariant_factor_decomposition
