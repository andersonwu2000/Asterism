import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
theorem span_preimage_eq_top
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K' : Set E} :
    Submodule.span ℝ ((Subtype.val : Submodule.span ℝ K' → E) ⁻¹' K') = ⊤ := by norm_num

end Problems.Topology.brouwer_fixed_point
