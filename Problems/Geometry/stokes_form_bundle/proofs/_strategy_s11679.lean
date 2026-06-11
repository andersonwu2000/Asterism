import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs.L_alternatization_exists_clm
import Problems.Geometry.stokes_form_bundle.proofs.L_comp_clm_eq_inv_factorial_smul
import Problems.Geometry.stokes_form_bundle.proofs.L_comp_diag_multilinear_contdiff

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

namespace Problems.Geometry.stokes_form_bundle

open scoped ContDiff

-- Factor the alternating pullback `g ↦ compContinuousLinearMapCLM g` through its multilinear
-- analogue: Mathlib's `compContinuousLinearMapContinuousMultilinear` is a continuous multilinear
-- map, hence `C^n`; precomposing with the diagonal `g ↦ (fun _ : ι ↦ g)` gives `h_diag`.
-- A bundled alternatization CLM `A` (sub-goal `alternatization_exists_clm`) is, after scaling by
-- `1/(card ι)!`, a continuous-linear left inverse of the inclusion of alternating into multilinear
-- maps, so the target equals a fixed CLM applied to the `C^n` multilinear-side map (`h_key`,
-- sub-goal `comp_clm_eq_inv_factorial_smul`); `clm_comp`/`const_smul` then close the goal.
theorem s11679
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι] {n : ℕ∞ω} :
    ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      (ContinuousAlternatingMap.compContinuousLinearMapCLM g :
        (F [⋀^ι]→L[ℝ] G) →L[ℝ] (E [⋀^ι]→L[ℝ] G)))  := by
  obtain ⟨A, hA⟩ := alternatization_exists_clm (E := E) (G := G) (ι := ι)
  have h_diag : ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
        (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)) :=
    comp_diag_multilinear_contdiff
  have h_key : ∀ g : E →L[ℝ] F,
      (ContinuousAlternatingMap.compContinuousLinearMapCLM g :
        (F [⋀^ι]→L[ℝ] G) →L[ℝ] (E [⋀^ι]→L[ℝ] G)) =
      ((Fintype.card ι).factorial : ℝ)⁻¹ •
        (A.comp
          ((ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
              (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)).comp
            (ContinuousAlternatingMap.toContinuousMultilinearMapCLM ℝ))) :=
    fun g ↦ comp_clm_eq_inv_factorial_smul A hA g
  have h_comp : ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      ((Fintype.card ι).factorial : ℝ)⁻¹ •
        (A.comp
          ((ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
              (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)).comp
            (ContinuousAlternatingMap.toContinuousMultilinearMapCLM ℝ)))) :=
    (contDiff_const.clm_comp (h_diag.clm_comp contDiff_const)).const_smul _
  rw [funext h_key]
  exact h_comp

end Problems.Geometry.stokes_form_bundle
