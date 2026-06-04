import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
-- subspace_preimage_props: preimage of K' under Subtype.val : V → E is nonempty/compact/convex/
-- contains 0, and homeomorphic to K', via the bijection x ↔ ⟨x, mem⟩ (isometric embedding).
theorem subspace_preimage_props
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K' : Set E} (V : Submodule ℝ E) (hK'V : K' ⊆ (V : Set E))
    (hne : K'.Nonempty) (hcomp : IsCompact K') (hconv : Convex ℝ K')
    (h0 : (0 : E) ∈ K') :
    ((Subtype.val : V → E) ⁻¹' K').Nonempty ∧
      IsCompact ((Subtype.val : V → E) ⁻¹' K') ∧
      Convex ℝ ((Subtype.val : V → E) ⁻¹' K') ∧
      (0 : V) ∈ ((Subtype.val : V → E) ⁻¹' K') ∧
      Nonempty (K' ≃ₜ ((Subtype.val : V → E) ⁻¹' K')) := by
  -- Subtype.val : V → E is an isometric embedding; build K' ≃ₜ preimage
  let e : K' ≃ₜ ((Subtype.val : V → E) ⁻¹' K') :=
    { toFun := fun ⟨x, hx⟩ => ⟨⟨x, hK'V hx⟩, hx⟩
      invFun := fun ⟨v, hv⟩ => ⟨v.val, hv⟩
      left_inv := fun ⟨_, _⟩ => rfl
      right_inv := fun ⟨⟨_, _⟩, _⟩ => rfl
      continuous_toFun := by fun_prop
      continuous_invFun := by fun_prop }
  refine ⟨?_, ?_, ?_, ?_, ?_⟩
  · exact ⟨⟨hne.some, hK'V hne.some_mem⟩, hne.some_mem⟩
  · rw [isCompact_iff_compactSpace]
    have := isCompact_iff_compactSpace.mp hcomp
    exact e.compactSpace
  · exact hconv.linear_preimage V.subtype
  · exact h0
  · exact ⟨e⟩

end Problems.Topology.brouwer_fixed_point