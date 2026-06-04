-- Off-diagonal repr-zero: reduce to the single component fact that the `i'`-th
-- summand of `X • eⱼₗ` vanishes (`lsmul_x_offdiag_component_zero`), since `i' ≠ j`
-- and the X-action is component-wise; the parent's `repr ... k'` layer then collapses
-- via `map_zero`. The sub-goal drops the outer `repr`/`k'` coordinate — strictly simpler.
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11599

namespace Problems.LinearAlgebra.rational_canonical_form

def lsmul_x_offdiag_repr_zero := @Problems.LinearAlgebra.rational_canonical_form.s11599

end Problems.LinearAlgebra.rational_canonical_form
