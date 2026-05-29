import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_endo_finrank_le_one_eq_det_smul

namespace Problems.Geometry.banach_tarski

-- Thin bridge over the proved scalar law `endo_finrank_le_one_eq_det_smul`:
-- restrict `T` to the ≤1-dim invariant `W`, so `T.restrict hinv : ↥W →ₗ ↥W`
-- acts as `(det) • ·`; `hdet` collapses the scalar to `1`, giving `T x = x` on `W`.
theorem s11427
    {n : ℕ} (T : EuclideanSpace ℝ (Fin n) ≃ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n))
    (W : Submodule ℝ (EuclideanSpace ℝ (Fin n)))
    (hinv : ∀ x ∈ W, T x ∈ W)
    (hr : Module.finrank ℝ W ≤ 1)
    (hdet : LinearMap.det
      ((T : EuclideanSpace ℝ (Fin n) →ₗ[ℝ] EuclideanSpace ℝ (Fin n)).restrict hinv) = 1) :
    ∀ x ∈ W, T x = x  := by
  intro x hx
  have h := endo_finrank_le_one_eq_det_smul
    ((T : EuclideanSpace ℝ (Fin n) →ₗ[ℝ] EuclideanSpace ℝ (Fin n)).restrict hinv) hr ⟨x, hx⟩
  rw [hdet, one_smul] at h
  have h2 := congrArg Subtype.val h
  simpa [LinearMap.restrict_apply] using h2

end Problems.Geometry.banach_tarski
