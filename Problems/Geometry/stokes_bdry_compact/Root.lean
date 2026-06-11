-- §6: the boundary `∂M` of a compact manifold-with-boundary is compact. Proof: the
-- boundary `(𝓡∂ (n+1)).boundary M` is a closed subset of `M` (model-with-corners
-- boundary is closed), and a closed subset of a compact space is compact.
import Mathlib
import Problems.Geometry.stokes_bdry_compact.Defs

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_bdry_compact

-- main: boundary of compact manifold-with-boundary is compact;
-- closed via isClosed_boundary (∞ ≠ 0), then IsClosed.isCompact + isCompact_iff_compactSpace
theorem main : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M], CompactSpace (Bdry n M) := by
  intro n M _ _ _ _ _
  unfold Bdry
  have hclosed : IsClosed ((𝓡∂ (n + 1)).boundary M) :=
    ModelWithCorners.isClosed_boundary (n := (∞ : WithTop ℕ∞))
      (by exact_mod_cast ENat.top_ne_zero)
  exact isCompact_iff_compactSpace.mp hclosed.isCompact

end Problems.Geometry.stokes_bdry_compact