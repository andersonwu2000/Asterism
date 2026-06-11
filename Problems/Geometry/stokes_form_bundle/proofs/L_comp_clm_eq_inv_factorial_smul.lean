import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

namespace Problems.Geometry.stokes_form_bundle

-- comp_clm_eq_inv_factorial_smul: compContinuousLinearMapCLM g factors through
-- alternatization of compContinuousLinearMapContinuousMultilinear composed with inclusion,
-- scaled by (card ι)!⁻¹, given that A acts as alternatization.
theorem comp_clm_eq_inv_factorial_smul
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (A : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G →L[ℝ] (E [⋀^ι]→L[ℝ] G))
    (hA : ∀ m, A m = ContinuousMultilinearMap.alternatization m)
    (g : E →L[ℝ] F) :
    (ContinuousAlternatingMap.compContinuousLinearMapCLM g :
      (F [⋀^ι]→L[ℝ] G) →L[ℝ] (E [⋀^ι]→L[ℝ] G)) =
    ((Fintype.card ι).factorial : ℝ)⁻¹ •
      (A.comp
        ((ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
            (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)).comp
          (ContinuousAlternatingMap.toContinuousMultilinearMapCLM ℝ))) := by
  have alt_fact : ∀ (h : E [⋀^ι]→L[ℝ] G),
      ContinuousMultilinearMap.alternatization h.toContinuousMultilinearMap =
      (Fintype.card ι).factorial • h := by
    intro h
    ext v
    simp only [ContinuousMultilinearMap.alternatization_apply_apply,
      ContinuousAlternatingMap.smul_apply,
      ContinuousAlternatingMap.coe_toContinuousMultilinearMap]
    have hperm : ∀ σ : Equiv.Perm ι, h (v ∘ ↑σ) = Equiv.Perm.sign σ • h v :=
      fun σ ↦ h.toAlternatingMap.map_perm v σ
    simp_rw [hperm]
    simp [smul_smul, Finset.sum_const, Fintype.card_perm]
  ext f
  simp only [ContinuousLinearMap.smul_apply, ContinuousLinearMap.comp_apply,
    ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
    ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear_apply_apply,
    ContinuousAlternatingMap.toContinuousMultilinearMapCLM_apply]
  rw [hA]
  have h1 : f.toContinuousMultilinearMap.compContinuousLinearMap (fun _ ↦ g) =
    (f.compContinuousLinearMap g).toContinuousMultilinearMap := rfl
  rw [h1, alt_fact, ← Nat.cast_smul_eq_nsmul ℝ, smul_smul,
    inv_mul_cancel₀ (Nat.cast_ne_zero.mpr (Nat.factorial_ne_zero _)), one_smul]

end Problems.Geometry.stokes_form_bundle
