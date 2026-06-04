import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_embed_into_span_submodule
import Problems.Topology.brouwer_fixed_point.proofs.L_translate_compact_convex_to_origin

namespace Problems.Topology.brouwer_fixed_point

-- Decompose: (1) translate K by -x₀ to a set K' ⊆ E containing 0 (homeomorphism preserved),
-- (2) embed K' into V := span K' as T ⊆ V satisfying nonempty/compact/convex/0∈T/span T = ⊤
-- and K' ≃ₜ T. Combine via K ≃ₜ K' ≃ₜ T. hns is unused at this level.
theorem s10815
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E}
    (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K)
    (hns : ¬ ∃ x : E, K = {x}) :
    ∃ (V : Submodule ℝ E) (T : Set V),
      T.Nonempty ∧ IsCompact T ∧ Convex ℝ T ∧
      (0 : V) ∈ T ∧ Submodule.span ℝ T = ⊤ ∧
      Nonempty (K ≃ₜ T)  := by
  have h_translate := translate_compact_convex_to_origin hne hcomp hconv
  obtain ⟨K', hK'ne, hK'comp, hK'conv, h0, ⟨hKK'⟩⟩ := h_translate
  have h_embed := embed_into_span_submodule hK'ne hK'comp hK'conv h0
  obtain ⟨V, T, hTne, hTcomp, hTconv, h0T, hspan, ⟨hK'T⟩⟩ := h_embed
  exact ⟨V, T, hTne, hTcomp, hTconv, h0T, hspan, ⟨hKK'.trans hK'T⟩⟩

end Problems.Topology.brouwer_fixed_point
