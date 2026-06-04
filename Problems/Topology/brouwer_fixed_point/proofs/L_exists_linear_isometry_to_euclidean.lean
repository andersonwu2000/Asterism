import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- stdOrthonormalBasis.repr gives the isometric equiv W ≃ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n)
theorem exists_linear_isometry_to_euclidean
    (W : Type*) [NormedAddCommGroup W] [InnerProductSpace ℝ W]
    [FiniteDimensional ℝ W] :
    ∃ (n : ℕ), Nonempty (W ≃ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n)) := by
  exact ⟨Module.finrank ℝ W, ⟨(stdOrthonormalBasis ℝ W).repr⟩⟩

end Problems.Topology.brouwer_fixed_point
