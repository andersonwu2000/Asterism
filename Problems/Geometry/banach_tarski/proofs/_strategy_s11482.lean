import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_letter0_head_flip

namespace Problems.Geometry.banach_tarski

-- Transport the F₂ identity `a·Wₐ⁻¹ = F₂\Wₐ` to point sets via the equivariant `wrd`.
-- The bijection `x ↦ φ(of 0)•x` on M has inverse `y ↦ φ((of 0)⁻¹)•y` (group/action algebra,
-- inline). Its only genuine-math content is the head-flip `letter0_head_flip`: for z∈M, the
-- word of `φ((of 0)⁻¹)•z` starts with `(0,false)` iff that of `z` does not start with `(0,true)`
-- (just `hwrd` + the proved sibling `head_inv_mul_iff`). Set.ext + this iff close both inclusions.
theorem s11482
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x) :
    (fun x => φ (FreeGroup.of 0) • x) ''
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)}
      = M \ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}  := by
  have key : ∀ z ∈ M,
      (FreeGroup.toWord (wrd (φ ((FreeGroup.of 0)⁻¹) • z))).head? = some (0, false)
        ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (0, true) :=
    fun z hz => letter0_head_flip φ M wrd hwrd z hz

  ext y
  simp only [Set.mem_image, Set.mem_setOf_eq, Set.mem_diff]
  constructor
  · rintro ⟨x, ⟨hxM, hxhead⟩, rfl⟩
    refine ⟨hinv _ _ hxM, ?_⟩
    rintro ⟨_, hhead⟩
    have hyM : φ (FreeGroup.of 0) • x ∈ M := hinv _ _ hxM
    have hxy : φ ((FreeGroup.of 0)⁻¹) • (φ (FreeGroup.of 0) • x) = x := by
      rw [smul_smul, ← map_mul, inv_mul_cancel, map_one, one_smul]
    have hk := key _ hyM
    rw [hxy] at hk
    exact (hk.mp hxhead) hhead
  · rintro ⟨hyM, hyhead⟩
    refine ⟨φ ((FreeGroup.of 0)⁻¹) • y, ⟨hinv _ _ hyM, ?_⟩, ?_⟩
    · rw [key y hyM]
      intro hc
      exact hyhead ⟨hyM, hc⟩
    · rw [smul_smul, ← map_mul, mul_inv_cancel, map_one, one_smul]


end Problems.Geometry.banach_tarski
