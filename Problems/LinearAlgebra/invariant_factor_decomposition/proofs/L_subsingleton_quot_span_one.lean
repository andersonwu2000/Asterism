import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- entry_kind: Builder
theorem subsingleton_quot_span_one {R : Type*} [CommRing R] :
    Subsingleton (R ⧸ Submodule.span R {(1 : R)}) := by norm_num

end Problems.LinearAlgebra.invariant_factor_decomposition
