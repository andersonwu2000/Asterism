import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- linear_isometry_image_set_props: packages nonempty/compact/convex/interior/homeo for a
-- linear isometric equivalence image of a set, via continuity, linearity, and open-map facts
-- entry_kind: Builder
theorem linear_isometry_image_set_props
    {W V : Type*} [NormedAddCommGroup W] [InnerProductSpace ℝ W]
    [NormedAddCommGroup V] [InnerProductSpace ℝ V]
    {T : Set W} (e : W ≃ₗᵢ[ℝ] V)
    (hTne : T.Nonempty) (hTcomp : IsCompact T) (hTconv : Convex ℝ T)
    (hTint : (interior T).Nonempty) :
    (e '' T).Nonempty ∧ IsCompact (e '' T) ∧ Convex ℝ (e '' T) ∧
        (interior (e '' T)).Nonempty ∧ Nonempty (T ≃ₜ (e '' T)) := by
  constructor
  · exact hTne.image e
  constructor
  · exact hTcomp.image e.toLinearIsometry.continuous
  constructor
  · have := hTconv.linear_image e.toLinearEquiv.toLinearMap
    simp only [LinearEquiv.coe_coe, LinearIsometryEquiv.coe_toLinearEquiv] at this
    exact this
  constructor
  · have h := e.toHomeomorph.isOpenMap.image_interior_subset T
    simp only [LinearIsometryEquiv.coe_toHomeomorph] at h
    exact (hTint.image e).mono h
  · have h : e.toHomeomorph '' T = e '' T := by
      simp [LinearIsometryEquiv.coe_toHomeomorph]
    exact ⟨(e.toHomeomorph.image T).trans (Homeomorph.setCongr h)⟩

end Problems.Topology.brouwer_fixed_point
