import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Direct leaf: pairwise-coprime principal ideals over the PID K[X] have
-- intersection = principal ideal of their product. Exactly mathlib's
-- `Ideal.iInf_span_singleton` (Submodule.span ≡ Ideal.span over a comm ring).
theorem s11570
    {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    (⨅ i, Submodule.span (Polynomial K) {g i})
      = Submodule.span (Polynomial K) {∏ i, g i}  :=
  Ideal.iInf_span_singleton hg

end Problems.LinearAlgebra.invariant_factor_decomposition
