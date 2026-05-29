import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- right_inv_hilbert: Hilbert-hotel right inverse law: f∘g = id on A\D,
-- using hshift (ρ''T = T\D) to show y∈T→ρ.symm y∈T, then f(ρ.symm y)=ρ(ρ.symm y)=y.
theorem right_inv_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f g : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (hshift : ρ '' T = T \ D) :
    ∀ y ∈ A \ D, f (g y) = y := by
  intro y hy
  simp only [Set.mem_diff] at hy
  obtain ⟨_, hyD⟩ := hy
  by_cases hyT : y ∈ T
  · have hgyT : ρ.symm y ∈ T := by
      have hy_in : y ∈ ρ '' T := by rw [hshift]; exact ⟨hyT, hyD⟩
      obtain ⟨x, hxT, hρxy⟩ := hy_in
      rwa [← hρxy, IsometryEquiv.symm_apply_apply]
    rw [hg y hyT, hf (ρ.symm y) hgyT, IsometryEquiv.apply_symm_apply]
  · rw [hg' y hyT, hf' y hyT]

end Problems.Geometry.banach_tarski

