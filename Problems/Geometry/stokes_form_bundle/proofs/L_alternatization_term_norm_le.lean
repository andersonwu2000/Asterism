import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

namespace Problems.Geometry.stokes_form_bundle

-- alternatization_term_norm_le: bounds ‖sign σ • m (v ∘ σ)‖ ≤ ‖m‖ * ∏ ‖v i‖ by case-splitting
-- on sign σ = ±1 (norm preserved), applying m.le_opNorm, and reindexing the product via σ.
theorem alternatization_term_norm_le
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G)
    (σ : Equiv.Perm ι) (v : ι → E) :
    ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ ≤ ‖m‖ * ∏ i, ‖v i‖ := by
  have h1 : ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ = ‖m (v ∘ σ)‖ := by
    rcases Int.isUnit_iff.mp (Units.isUnit (Equiv.Perm.sign σ)) with h | h
    · have : Equiv.Perm.sign σ = 1 := Units.val_eq_one.mp (by exact_mod_cast h)
      simp [this]
    · have : Equiv.Perm.sign σ = -1 := Units.ext h
      simp [this, norm_neg]
  have h2 : ‖m (v ∘ σ)‖ ≤ ‖m‖ * ∏ i, ‖(v ∘ σ) i‖ := m.le_opNorm _
  have h3 : ∏ i, ‖(v ∘ σ) i‖ = ∏ i, ‖v i‖ := by
    simp only [Function.comp]
    exact Finset.prod_equiv σ (by simp) (by simp)
  linarith [h1.symm ▸ h2.trans (le_of_eq (by rw [h3]))]
end Problems.Geometry.stokes_form_bundle
