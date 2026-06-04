import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- affine_span_eq_top_of_zero_mem: bridge linear span = ⊤ + 0 ∈ T to affine span = ⊤
-- When 0 ∈ T, vectorSpan ℝ T = Submodule.span ℝ T; direction = ⊤ then forces affineSpan = ⊤
theorem affine_span_eq_top_of_zero_mem
    {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℝ V]
    [FiniteDimensional ℝ V] {T : Set V}
    (hTne : T.Nonempty) (hTcomp : IsCompact T) (hTconv : Convex ℝ T)
    (h0 : (0 : V) ∈ T) (hspan : Submodule.span ℝ T = ⊤) :
    affineSpan ℝ T = ⊤ := by
  have hvspan : vectorSpan ℝ T = Submodule.span ℝ T := by
    apply le_antisymm
    · rw [vectorSpan_def]
      apply Submodule.span_le.mpr
      intro v hv
      simp only [Set.mem_vsub] at hv
      obtain ⟨a, ha, b, hb, rfl⟩ := hv
      simp only [vsub_eq_sub]
      exact Submodule.sub_mem _ (Submodule.subset_span ha) (Submodule.subset_span hb)
    · apply Submodule.span_le.mpr
      intro v hv
      have : v -ᵥ (0 : V) ∈ vectorSpan ℝ T := vsub_mem_vectorSpan ℝ hv h0
      simpa using this
  have hd : (affineSpan ℝ T).direction = ⊤ := by
    rw [direction_affineSpan, hvspan, hspan]
  have hmem0 : (0 : V) ∈ affineSpan ℝ T := subset_affineSpan ℝ T h0
  ext x
  simp only [AffineSubspace.mem_top, iff_true]
  have hxeq : x = x +ᵥ (0 : V) := by simp
  rw [hxeq, AffineSubspace.vadd_mem_iff_mem_direction x hmem0]
  simp [hd]

end Problems.Topology.brouwer_fixed_point

