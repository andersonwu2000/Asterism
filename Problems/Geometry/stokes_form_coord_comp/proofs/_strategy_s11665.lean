import Mathlib
import Problems.Geometry.stokes_form_coord_comp.Defs

namespace Problems.Geometry.stokes_form_coord_comp

open scoped Manifold Bundle ContDiff

-- Direct proof (leaf bypass): extensionality + simp-unfold of `formCoordChange`
-- reduces both sides to pointwise applications of `v`; `congr`/`funext` exposes the
-- tangent transition cocycle, closed by `(tangentBundleCore I M).coordChange_comp`
-- with indices `(l, j, i)` (contravariant index swap in `formCoordChange`).
theorem s11665 : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    (k : ℕ) (i j l : atlas H M),
    ∀ x ∈ (tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j
        ∩ (tangentBundleCore I M).baseSet l, ∀ v,
      formCoordChange I k j l x (formCoordChange I k i j x v)
        = formCoordChange I k i l x v  := by
  intro E _ _ H _ I M _ _ _ k i j l x hx v
  obtain ⟨⟨hi, hj⟩, hl⟩ := hx
  ext m
  simp only [formCoordChange,
    ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
    ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1
  funext u
  simp only [Function.comp_apply]
  exact (tangentBundleCore I M).coordChange_comp l j i x ⟨⟨hl, hj⟩, hi⟩ (m u)

end Problems.Geometry.stokes_form_coord_comp
