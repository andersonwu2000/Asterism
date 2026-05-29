import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- free_action_word_unique: freeness of φ forces a = b when φ a • y = φ b • y (y ∈ M)
-- Apply hfree to a⁻¹ * b: φ(a⁻¹*b)•y = (φa)⁻¹•(φb•y) = (φa)⁻¹•(φa•y) = y forces a⁻¹*b=1.
-- entry_kind: Builder

theorem free_action_word_unique
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (y : E) (hy : y ∈ M) (a b : FreeGroup (Fin 2)) (h : φ a • y = φ b • y) :
    a = b := by
  -- φ a • y = φ b • y implies φ(a⁻¹*b) • y = y, hence a⁻¹*b = 1 by freeness, so b = a
  have key : a⁻¹ * b = 1 := by
    by_contra hne
    exact hfree (a⁻¹ * b) hne y hy (by
      rw [map_mul, mul_smul, map_inv, ← h, inv_smul_smul])
  exact inv_mul_eq_one.mp key

end Problems.Geometry.banach_tarski
