/-
  Defs.lean — shared vocabulary for the `instBdryCompact` obligation (§6 of the
  Stokes construction): the boundary subtype `∂M` and its topology. The lemma to
  prove (∂M is compact) is the Root.
-/
import Mathlib

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_bdry_compact

/-- The boundary `∂M` as a subtype of `M`. -/
def Bdry (n : ℕ) (M : Type*) [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M] : Type _ :=
  {x : M // x ∈ (𝓡∂ (n + 1)).boundary M}

instance {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M] :
    TopologicalSpace (Bdry n M) :=
  inferInstanceAs (TopologicalSpace {x : M // x ∈ (𝓡∂ (n + 1)).boundary M})

end Problems.Geometry.stokes_bdry_compact
