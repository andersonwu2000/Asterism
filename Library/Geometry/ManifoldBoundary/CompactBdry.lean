import Mathlib.Data.ENat.Basic
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Topology.Compactness.Compact

/-!
# Boundary of a compact manifold-with-boundary

This file proves that the boundary of a compact manifold-with-boundary is itself compact.

## Main definitions

- `Bdry`: the subtype of boundary points of an `n`-dimensional manifold-with-boundary.

## Main statements

- `compactSpace_bdry`: the boundary of a compact manifold-with-boundary is a compact space.
-/

open Bundle
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBoundary.CompactBdry

/-- The boundary of an `n`-dimensional manifold-with-boundary `M`, as a subtype. -/
def Bdry (n : ℕ) (M : Type*) [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M] : Type _ :=
  {x : M // x ∈ (𝓡∂ (n + 1)).boundary M}

instance instTopologicalSpaceBdry {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M] :
    TopologicalSpace (Bdry n M) :=
  inferInstanceAs (TopologicalSpace {x : M // x ∈ (𝓡∂ (n + 1)).boundary M})

/-- The boundary of a compact manifold-with-boundary is compact. The boundary is closed
via `ModelWithCorners.isClosed_boundary` (using `∞ ≠ 0`), and a closed subspace of a
compact space is compact. -/
theorem compactSpace_bdry {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M] : CompactSpace (Bdry n M) := by
  unfold Bdry
  have hclosed : IsClosed ((𝓡∂ (n + 1)).boundary M) :=
    ModelWithCorners.isClosed_boundary (n := (∞ : WithTop ℕ∞))
      (by exact_mod_cast ENat.top_ne_zero)
  exact isCompact_iff_compactSpace.mp hclosed.isCompact

end Library.Geometry.ManifoldBoundary.CompactBdry
