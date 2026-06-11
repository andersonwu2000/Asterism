import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs

namespace Problems.Geometry.stokes_form_bundle

open scoped ContDiff

-- Direct proof: the map is a continuous multilinear map composed with the diagonal CLM,
-- hence continuously polynomial, hence C^n via `CPolynomialAt.contDiffAt` —
-- bypassing `ContDiff.comp` whose instance unification times out here (per problem lessons).
theorem s11684
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] {n : ℕ∞ω} :
    ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
        (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g))  := by
  refine contDiff_iff_contDiffAt.mpr fun x ↦ ?_
  have hM : CPolynomialAt ℝ
      (ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
        (fun _ : ι ↦ E) (fun _ : ι ↦ F) G) (fun _ ↦ x) :=
    ContinuousMultilinearMap.cpolynomialAt _
  have hdiag : CPolynomialAt ℝ (fun g : E →L[ℝ] F ↦ (fun _ : ι ↦ g)) x :=
    (ContinuousLinearMap.pi fun _ : ι ↦ ContinuousLinearMap.id ℝ (E →L[ℝ] F)).cpolynomialAt x
  exact (hM.fun_comp hdiag).contDiffAt

end Problems.Geometry.stokes_form_bundle
