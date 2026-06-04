import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_fixed_point_subtype_via_homeo
import Problems.Topology.brouwer_fixed_point.proofs.L_restricted_self_map_continuous

namespace Problems.Topology.brouwer_fixed_point

-- Restrict f to a subtype self-map of S, then transfer the Brouwer-on-T
-- fixed-point fact across `φ : S ≃ₜ T` by conjugation.
-- Sub-goal `restricted_self_map_continuous` packages continuity of the
-- subtype restriction of `f`; sub-goal `fixed_point_subtype_via_homeo`
-- is the abstract conjugation-by-homeomorphism transfer.
theorem s10829
    {α β : Type*} [TopologicalSpace α] [TopologicalSpace β]
    {S : Set α} {T : Set β}
    (φ : S ≃ₜ T)
    {f : α → α} (_hcont : ContinuousOn f S) (_hmaps : Set.MapsTo f S S)
    (_hbrouwer : ∀ (g : T → T), Continuous g → ∃ y, g y = y) :
    ∃ x ∈ S, f x = x  := by
  have h_restrict := restricted_self_map_continuous _hcont _hmaps
  obtain ⟨x, hx⟩ :=
    fixed_point_subtype_via_homeo φ
      (fun s => ⟨f s.val, _hmaps s.property⟩) h_restrict _hbrouwer
  refine ⟨x.val, x.property, ?_⟩
  have := congrArg Subtype.val hx
  exact this

end Problems.Topology.brouwer_fixed_point
