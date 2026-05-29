import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_head_inv_mul_iff

namespace Problems.Geometry.banach_tarski

-- Generator-1 analogue of `letter0_split`/s11482: transport the F₂ identity
-- `b·Wᵦ⁻¹ = M\Wᵦ` to point sets via the equivariant `wrd`. The bijection
-- `x ↦ φ(of 1)•x` on M has inverse `y ↦ φ((of 1)⁻¹)•y` (group/action algebra,
-- inline). Genuine content is the head-flip `key`: `hwrd` + proved sibling
-- `head_inv_mul_iff 1`. `Set.ext` + this iff close both inclusions. No sub-goals.
theorem s11489
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x) :
    (fun x => φ (FreeGroup.of 1) • x) ''
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)}
      = M \ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)}  := by
  have key : ∀ z ∈ M,
      (FreeGroup.toWord (wrd (φ ((FreeGroup.of 1)⁻¹) • z))).head? = some (1, false)
        ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (1, true) := by
    intro z hz
    rw [hwrd z hz]
    exact head_inv_mul_iff 1 (wrd z)
  ext y
  simp only [Set.mem_image, Set.mem_setOf_eq, Set.mem_diff]
  constructor
  · rintro ⟨x, ⟨hxM, hxhead⟩, rfl⟩
    refine ⟨hinv _ _ hxM, ?_⟩
    rintro ⟨_, hhead⟩
    have hyM : φ (FreeGroup.of 1) • x ∈ M := hinv _ _ hxM
    have hxy : φ ((FreeGroup.of 1)⁻¹) • (φ (FreeGroup.of 1) • x) = x := by
      rw [smul_smul, ← map_mul, inv_mul_cancel, map_one, one_smul]
    have hk := key _ hyM
    rw [hxy] at hk
    exact (hk.mp hxhead) hhead
  · rintro ⟨hyM, hyhead⟩
    refine ⟨φ ((FreeGroup.of 1)⁻¹) • y, ⟨hinv _ _ hyM, ?_⟩, ?_⟩
    · rw [key y hyM]
      intro hc
      exact hyhead ⟨hyM, hc⟩
    · rw [smul_smul, ← map_mul, mul_inv_cancel, map_one, one_smul]

end Problems.Geometry.banach_tarski
