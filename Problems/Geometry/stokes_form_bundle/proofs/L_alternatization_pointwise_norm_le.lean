import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

namespace Problems.Geometry.stokes_form_bundle

-- alternatization_pointwise_norm_le: expand via alternatization_apply_apply then
-- bound via norm_sum_le + h_term + Fintype.card_perm.
theorem alternatization_pointwise_norm_le
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G)
    (h_term : ∀ (σ : Equiv.Perm ι) (v : ι → E),
      ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ ≤ ‖m‖ * ∏ i, ‖v i‖)
    (v : ι → E) :
    ‖(ContinuousMultilinearMap.alternatization m : E [⋀^ι]→L[ℝ] G) v‖
      ≤ ((Nat.factorial (Fintype.card ι)) : ℝ) * ‖m‖ * ∏ i, ‖v i‖ := by
  rw [ContinuousMultilinearMap.alternatization_apply_apply]
  calc ‖∑ σ : Equiv.Perm ι, Equiv.Perm.sign σ • m (v ∘ σ)‖
      ≤ ∑ σ : Equiv.Perm ι, ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ := norm_sum_le _ _
    _ ≤ ∑ _σ : Equiv.Perm ι, ‖m‖ * ∏ i, ‖v i‖ :=
          Finset.sum_le_sum (fun σ _ => h_term σ v)
    _ = Fintype.card (Equiv.Perm ι) * (‖m‖ * ∏ i, ‖v i‖) := by
          simp [Finset.sum_const, Finset.card_univ]
    _ = ((Nat.factorial (Fintype.card ι)) : ℝ) * ‖m‖ * ∏ i, ‖v i‖ := by
          rw [Fintype.card_perm]; ring

end Problems.Geometry.stokes_form_bundle
