import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_head_inv_mul_iff

namespace Problems.Geometry.banach_tarski

-- letter0_head_flip: applies hwrd then head_inv_mul_iff to close the head-character flip
theorem letter0_head_flip
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x)
    (z : E) (hz : z ∈ M) :
    (FreeGroup.toWord (wrd (φ ((FreeGroup.of 0)⁻¹) • z))).head? = some (0, false)
      ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (0, true) := by
  rw [hwrd z hz]
  exact head_inv_mul_iff 0 (wrd z)

end Problems.Geometry.banach_tarski
