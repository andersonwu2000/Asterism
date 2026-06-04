import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_convex_compact_span_top_has_interior
import Problems.Topology.brouwer_fixed_point.proofs.L_translate_into_subspace_at_zero

namespace Problems.Topology.brouwer_fixed_point

-- Decompose: pick x₀ ∈ K, translate K so that 0 lies inside, embed into V := span(K - x₀);
-- then interior-in-V follows from the abstract fact that a convex compact set containing 0
-- whose linear span is the ambient finite-dim space has nonempty interior.
-- Sub_1 (translate_into_subspace_at_zero) packages the construction (homeomorphism + spanning).
-- Sub_2 (convex_compact_span_top_has_interior) is a pure abstract dimension/interior fact —
-- independent of K, with no homeomorphism reasoning.
theorem s10814
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E}
    (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K)
    (hns : ¬ ∃ x : E, K = {x}) :
    ∃ (V : Submodule ℝ E) (T : Set V),
      T.Nonempty ∧ IsCompact T ∧ Convex ℝ T ∧ (interior T).Nonempty ∧
        Nonempty (K ≃ₜ T)  := by
  have h_translate := translate_into_subspace_at_zero hne hcomp hconv hns
  obtain ⟨V, T, hTne, hTcomp, hTconv, h0, hspan, hKT⟩ := h_translate
  have hTint := convex_compact_span_top_has_interior hTne hTcomp hTconv h0 hspan
  exact ⟨V, T, hTne, hTcomp, hTconv, hTint, hKT⟩

end Problems.Topology.brouwer_fixed_point
