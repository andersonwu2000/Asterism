import Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
import Mathlib

open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBoundary.Defs

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- Drop coordinate `0` (the normal): the left inverse of `faceEmbed`. -/
noncomputable def faceProj (w : EuclideanSpace ℝ (Fin (n + 1))) : EuclideanSpace ℝ (Fin n) :=
  (EuclideanSpace.equiv (Fin n) ℝ).symm (fun i => w i.succ)

/-- `toFun` of the boundary chart at `p`: `M`'s extended chart, projected to the face. -/
noncomputable def chartToFun (p : Bdry n M) (q : Bdry n M) : EuclideanSpace ℝ (Fin n) :=
  faceProj (extChartAt (𝓡∂ (n + 1)) p.val q.val)

/-- `source` of the boundary chart at `p`. -/
noncomputable def chartSource (p : Bdry n M) : Set (Bdry n M) :=
  Subtype.val ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).source

/-- `target` of the boundary chart at `p`: project the face slice of the chart target. -/
noncomputable def chartTarget (p : Bdry n M) : Set (EuclideanSpace ℝ (Fin n)) :=
  faceProj '' ((extChartAt (𝓡∂ (n + 1)) p.val).target ∩ {w | w 0 = 0})

/-- `invFun` of the boundary chart at `p`: guarded so off-target `z` lands at `p`
    (a boundary point); on-target the membership is the cited Library lemma. -/
noncomputable def chartInvFun (p : Bdry n M) (z : EuclideanSpace ℝ (Fin n)) : Bdry n M :=
  haveI : Decidable (faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target) :=
    Classical.propDecidable _
  if h : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target then
    ⟨(extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z), faceEmbed_symm_mem_boundary p z h⟩
  else p

end Library.Geometry.ManifoldBoundary.Defs
