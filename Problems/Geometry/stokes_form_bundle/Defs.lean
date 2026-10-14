/-
  Defs.lean — owns the `⋀ᵏ T*M` vector bundle: `formBundleCore` (built from the
  cited `formCoordChange` + its three coherence lemmas), the fibre/vector-bundle
  instances, and `DiffForm` (smooth sections = differential forms). Cites
  `Problems.Geometry.stokes_form_coord_{comp,self,cont}`. The Root proves the core's
  transitions are `C^∞`.
-/
import Mathlib
import Problems.Geometry.stokes_form_coord_comp.Defs
import Problems.Geometry.stokes_form_coord_comp.Root
import Problems.Geometry.stokes_form_coord_cont.Root
import Problems.Geometry.stokes_form_coord_self.Root

open scoped Manifold Bundle ContDiff
open Bundle
open Problems.Geometry.stokes_form_coord_comp (formCoordChange)

namespace Problems.Geometry.stokes_form_bundle

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- The vector-bundle core of `⋀ᵏ T*M`. Coherence fields are the cited Library
    lemmas (no `sorry`); the base structure is the tangent core's. -/
noncomputable def formBundleCore (k : ℕ) :
    VectorBundleCore ℝ M (E [⋀^Fin k]→L[ℝ] ℝ) (atlas H M) where
  baseSet i := (tangentBundleCore I M).baseSet i
  isOpen_baseSet i := (tangentBundleCore I M).isOpen_baseSet i
  indexAt := (tangentBundleCore I M).indexAt
  mem_baseSet_at := (tangentBundleCore I M).mem_baseSet_at
  coordChange := formCoordChange I k
  coordChange_self := Problems.Geometry.stokes_form_coord_self.main I k
  continuousOn_coordChange := Problems.Geometry.stokes_form_coord_cont.main I k
  coordChange_comp := Problems.Geometry.stokes_form_coord_comp.main I k

/-- Fibre-bundle instance for `⋀ᵏ T*M` (declared on the `.Fiber` expression). -/
noncomputable instance instFormFiberBundle (k : ℕ) :
    FiberBundle (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber :=
  (formBundleCore (M := M) I k).fiberBundle

/-- Vector-bundle instance for `⋀ᵏ T*M`. -/
noncomputable instance instFormVectorBundle (k : ℕ) :
    VectorBundle ℝ (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber :=
  (formBundleCore (M := M) I k).vectorBundle

/-- A smooth differential `k`-form on `M`: a `C^∞` section of `⋀ᵏ T*M`. `I`/`M`
    explicit (mathlib idiom for section type-formers). -/
abbrev DiffForm (I : ModelWithCorners ℝ E H) (M : Type*) [TopologicalSpace M]
    [ChartedSpace H M] [IsManifold I ∞ M] (k : ℕ) : Type _ :=
  Cₛ^∞⟮I; (E [⋀^Fin k]→L[ℝ] ℝ), (formBundleCore (M := M) I k).Fiber⟯

end Problems.Geometry.stokes_form_bundle
