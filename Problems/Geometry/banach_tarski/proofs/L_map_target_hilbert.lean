import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- map_target_hilbert: g (= ρ⁻¹ on T, id off T) maps A \ D into A.
-- Key: y ∈ T ∧ y ∉ D  →  y ∈ T \ D = ρ '' T  →  ρ.symm y ∈ T ⊆ A;
-- y ∉ T  →  g y = y ∈ A.
theorem map_target_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (g : E → E)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (_hDT : D ⊆ T) (hTA : T ⊆ A) (hshift : ρ '' T = T \ D) :
    ∀ y ∈ A \ D, g y ∈ A := by
  intro y ⟨hyA, hyD⟩
  by_cases hyT : y ∈ T
  · rw [hg y hyT]
    have hy_shift : y ∈ ρ '' T := by rw [hshift]; exact ⟨hyT, hyD⟩
    obtain ⟨z, hz, hρz⟩ := hy_shift
    rw [← hρz, IsometryEquiv.symm_apply_apply]
    exact hTA hz
  · rw [hg' y hyT]; exact hyA

end Problems.Geometry.banach_tarski
