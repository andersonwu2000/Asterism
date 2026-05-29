import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Backward
-- wrd_of_tower_image: FreeGroup cohomology — word address of tower image equals group power
-- For z = (φ(of 1)⁻¹)^k • x with wrd x = 1 (head? = none), hcoh gives wrd z = (of 1)⁻¹^k * 1.
theorem wrd_of_tower_image
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x)
    (k : ℕ) (z : E)
    (hz : z ∈ ((φ (FreeGroup.of 1))⁻¹ ^ k) ''
        {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}) :
    wrd z = ((FreeGroup.of (1:Fin 2))⁻¹) ^ k := by
  obtain ⟨x, ⟨hxM, hhead⟩, rfl⟩ := hz
  have hnil : FreeGroup.toWord (wrd x) = [] := by
    cases h : FreeGroup.toWord (wrd x) with
    | nil => rfl
    | cons a t => simp [h] at hhead
  have hwrd_x : wrd x = 1 := by
    apply FreeGroup.toWord_injective
    rw [hnil, FreeGroup.toWord_one]
  have hkey : ((φ (FreeGroup.of 1))⁻¹ ^ k) x =
      φ ((FreeGroup.of (1:Fin 2))⁻¹ ^ k) • x := by
    simp only [map_pow, map_inv]; rfl
  rw [hkey]
  have hcoh2 := (hcoh x hxM ((FreeGroup.of (1:Fin 2))⁻¹ ^ k)).2
  rw [hwrd_x, mul_one] at hcoh2
  exact hcoh2

end Problems.Geometry.banach_tarski
