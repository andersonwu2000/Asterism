import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_exists_linear_isometry_to_euclidean
import Problems.Topology.brouwer_fixed_point.proofs.L_linear_isometry_image_set_props

namespace Problems.Topology.brouwer_fixed_point

-- Use the orthonormal-basis-induced linear isometric equivalence
-- `W ≃ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n)` (sub_1, where n = finrank ℝ W) and
-- transport `T` along it. Sub_2 packages the standard preservation facts
-- (image is nonempty/compact/convex with nonempty interior, plus the homeo
-- restriction from e) into one bundle, so the parent is closed by a single
-- ⟨n, e '' T, _⟩ witness. Each sub-goal is strictly simpler: sub_1 is a
-- direct application of Mathlib's `OrthonormalBasis.toLinearIsometryEquiv`
-- (no set-theoretic content), sub_2 is generic in `V` and re-uses
-- continuity/openness/linearity of `e` without touching the existential.
theorem s10813
    {W : Type*} [NormedAddCommGroup W] [InnerProductSpace ℝ W]
    [FiniteDimensional ℝ W] {T : Set W}
    (hTne : T.Nonempty) (hTcomp : IsCompact T) (hTconv : Convex ℝ T)
    (hTint : (interior T).Nonempty) :
    ∃ (n : ℕ) (S : Set (EuclideanSpace ℝ (Fin n))),
      S.Nonempty ∧ IsCompact S ∧ Convex ℝ S ∧ (interior S).Nonempty ∧
        Nonempty (T ≃ₜ S)  := by
  have h_iso := exists_linear_isometry_to_euclidean W
  obtain ⟨n, ⟨e⟩⟩ := h_iso
  have h_props := linear_isometry_image_set_props e hTne hTcomp hTconv hTint
  exact ⟨n, e '' T, h_props⟩

end Problems.Topology.brouwer_fixed_point
