-- The `X`-scalar action on `⨁ᵢ K[X]/(fᵢ)` has matrix `blockDiagonal'` of the per-block
-- companion (`mulLeft (root fᵢ)`) matrices, in the `DFinsupp.basis` of power bases.
-- Entry-wise (`ext ⟨i,k⟩ ⟨j,l⟩`, `toMatrix_apply`): `dfinsupp_basis_repr_component` pushes
-- the `repr` into the `i`-th summand; then `by_cases i = j`. The diagonal entry is the
-- single-block companion value (`lsmul_x_diag_component` + `blockDiagonal'_apply_eq`); the
-- off-diagonal `repr` vanishes (`lsmul_x_offdiag_repr_zero` + `blockDiagonal'_apply_ne`)
-- because each cyclic summand is invariant under the `X`-action. Each sub-goal is a single
-- component identity over one (or two) summands — strictly smaller than the full matrix.
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11595

namespace Problems.LinearAlgebra.rational_canonical_form

def block_diag := @Problems.LinearAlgebra.rational_canonical_form.s11595

end Problems.LinearAlgebra.rational_canonical_form
