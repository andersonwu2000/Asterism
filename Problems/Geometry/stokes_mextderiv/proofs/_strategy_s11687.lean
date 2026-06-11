import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle

-- Direct sorry-free proof: the trivialization at x₀ has baseSet defeq to (chartAt H x₀).source,
-- so the trivialized read of the smooth section φ is ContMDiffOn there by mathlib's
-- Trivialization.contMDiffOn_section_iff applied to φ.contMDiff; the goal's
-- continuousLinearMapAt wrapper agrees pointwise via continuousLinearMapAt_apply_of_mem.
theorem s11687
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun p ↦ Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x₀) p (φ p))
      ((chartAt H x₀).source)  := by
  have h_base : (chartAt H x₀).source ⊆
      (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x₀).baseSet := by
    exact subset_rfl
  have h_snd : ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun p ↦ ((trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ)
          (formBundleCore (M := M) I k).Fiber x₀) ⟨p, φ p⟩).2)
      ((chartAt H x₀).source) := by
    exact (Trivialization.contMDiffOn_section_iff _ (chartAt H x₀).open_source h_base).mp
      φ.contMDiff.contMDiffOn
  refine h_snd.congr fun p hp ↦ ?_
  exact Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ (h_base hp) (φ p)

end Problems.Geometry.stokes_mextderiv
