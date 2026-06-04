import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- translate_compact_convex_to_origin: translate K by -x₀ to get K' containing 0, homeomorphic to K
-- Uses Homeomorph.addLeft (-x₀) (maps x ↦ -x₀ + x) so Convex.translate applies directly.
-- entry_kind: Builder
theorem translate_compact_convex_to_origin
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E}
    (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K) :
    ∃ (K' : Set E), K'.Nonempty ∧ IsCompact K' ∧ Convex ℝ K' ∧
      (0 : E) ∈ K' ∧ Nonempty (K ≃ₜ K') := by
  obtain ⟨x₀, hx₀⟩ := hne
  let e := Homeomorph.addLeft (-x₀)
  refine ⟨e '' K, ?_, hcomp.image e.continuous, hconv.translate (-x₀), ?_, ⟨e.image K⟩⟩
  · exact ⟨e x₀, Set.mem_image_of_mem _ hx₀⟩
  · exact ⟨x₀, hx₀, by simp [e, Homeomorph.addLeft]⟩

end Problems.Topology.brouwer_fixed_point
