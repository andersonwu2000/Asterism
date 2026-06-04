import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_realize_in_subspace_with_interior
import Problems.Topology.brouwer_fixed_point.proofs.L_subspace_set_homeo_euclidean_image

namespace Problems.Topology.brouwer_fixed_point

-- Decompose: realize K in a (Submodule) subspace V of E with nonempty interior in V,
-- then transport that "fat" subset to a Euclidean coordinate space via an isometry
-- supplied by the orthonormal-basis machinery on finite-dim inner product spaces.
-- Sub_1 isolates the affine-span / interior-in-its-own-span argument; sub_2 is a
-- straight transport along a known Mathlib isomorphism, with no convexity-from-span
-- reasoning involved.
theorem s10810
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E}
    (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K)
    (hns : ¬ ∃ x : E, K = {x}) :
    ∃ (n : ℕ) (S : Set (EuclideanSpace ℝ (Fin n))),
      S.Nonempty ∧ IsCompact S ∧ Convex ℝ S ∧ (interior S).Nonempty ∧
        Nonempty (K ≃ₜ S)  := by
  have h_realize_in_subspace_with_interior :=
    realize_in_subspace_with_interior hne hcomp hconv hns
  obtain ⟨V, T, hTne, hTcomp, hTconv, hTint, ⟨hKT⟩⟩ :=
    h_realize_in_subspace_with_interior
  have h_subspace_set_homeo_euclidean_image :=
    subspace_set_homeo_euclidean_image hTne hTcomp hTconv hTint
  obtain ⟨n, S, hSne, hScomp, hSconv, hSint, ⟨hTS⟩⟩ :=
    h_subspace_set_homeo_euclidean_image
  exact ⟨n, S, hSne, hScomp, hSconv, hSint, ⟨hKT.trans hTS⟩⟩

end Problems.Topology.brouwer_fixed_point
