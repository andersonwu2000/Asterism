-- Off-diagonal component vanishes: the X-action on the direct sum is component-wise,
-- so the i'-th component of `X • eⱼₗ` is `X • (eⱼₗ i')`. The basis vector `eⱼₗ` is
-- supported only on summand `j`, hence its i'-th component (i' ≠ j) is `0`
-- (sub-goal `dfinsupp_basis_offdiag_component_zero`, a pure basis-support fact stripped
-- of the lsmul/restrictScalars layers); `convert smul_zero` then collapses `X • 0`.
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11600

namespace Problems.LinearAlgebra.rational_canonical_form

def lsmul_x_offdiag_component_zero := @Problems.LinearAlgebra.rational_canonical_form.s11600

end Problems.LinearAlgebra.rational_canonical_form
