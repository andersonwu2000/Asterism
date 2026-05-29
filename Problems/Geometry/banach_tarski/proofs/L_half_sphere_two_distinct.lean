import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- half_sphere_two_distinct: two explicit antipodal points witness the radius-1/2 sphere is nonempty
-- Uses EuclideanSpace.single to build (1/2,0,0) and (-1/2,0,0); norm computed by simp,
-- distinctness by extracting the 0th coordinate and norm_num.
theorem half_sphere_two_distinct :
    ∃ p q : E, p ∈ Metric.sphere (0 : E) (1 / 2) ∧
      q ∈ Metric.sphere (0 : E) (1 / 2) ∧ p ≠ q := by
  refine ⟨EuclideanSpace.single (0 : Fin 3) (1/2 : ℝ),
          EuclideanSpace.single (0 : Fin 3) (-1/2 : ℝ), ?_, ?_, ?_⟩
  · simp
  · simp
  · intro h
    have h0 : (EuclideanSpace.single (0 : Fin 3) (1/2 : ℝ)).ofLp (0 : Fin 3) =
              (EuclideanSpace.single (0 : Fin 3) (-1/2 : ℝ)).ofLp (0 : Fin 3) :=
      congr_arg (fun x => x.ofLp 0) h
    simp at h0
    norm_num at h0

end Problems.Geometry.banach_tarski