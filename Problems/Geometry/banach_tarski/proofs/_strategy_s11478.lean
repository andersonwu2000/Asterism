import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_rotation_word_ne_one_of_reduced
import Problems.Geometry.banach_tarski.proofs.L_gen_a_det_one
import Problems.Geometry.banach_tarski.proofs.L_gen_b_det_one
import Problems.Geometry.banach_tarski.proofs.L_lift_det_one
import Problems.Geometry.banach_tarski.proofs.L_lift_ne_one
import Problems.Geometry.banach_tarski.proofs.L_so3_realization_hom

namespace Problems.Geometry.banach_tarski

-- Build ψ := FreeGroup.lift g, where g : Fin 2 → (E ≃ₗᵢ[ℝ] E) are the two rotation
-- generators realized through a monoid hom `mat` to 3×3 matrices (the SO(3) embedding).
-- so3_realization_hom supplies g, mat (injective, det-preserving) with mat(g i)/(mat(g i))⁻¹
-- equal to the four concrete generator matrices. Then per nontrivial word w:
--   • det = 1: mat preserves det and every generator-matrix has det 1  (lift_det_one)
--   • ψ w ≠ refl(=1): the matrix word-product ≠ 1 (rotation_word_ne_one_of_reduced, s11407)
--     transported back through injectivity of mat  (lift_ne_one)
-- injectivity of ψ is the same ne-one fact via injective_iff_map_eq_one.
theorem s11478 :
    ∃ ψ : FreeGroup (Fin 2) →* (E ≃ₗᵢ[ℝ] E),
      Function.Injective ψ ∧
      (∀ w : FreeGroup (Fin 2), w ≠ 1 →
        LinearMap.det ((ψ w).toLinearEquiv.toLinearMap) = 1 ∧
        ψ w ≠ LinearIsometryEquiv.refl ℝ E)  := by
  obtain ⟨g, mat, hmatinj, hmatdet, hg0, hg0inv, hg1, hg1inv⟩ := so3_realization_hom
  have hdetA : (mat (g 0)).det = 1 := by rw [hg0]; exact gen_a_det_one
  have hdetB : (mat (g 1)).det = 1 := by rw [hg1]; exact gen_b_det_one
  have hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then mat (g 0) else (mat (g 0))⁻¹)
                    else (if x.2 then mat (g 1) else (mat (g 1))⁻¹))).prod ≠ 1 := by
    intro w hw
    simp only [hg0inv, hg1inv]
    simp only [hg0, hg1]
    exact rotation_word_ne_one_of_reduced _ _ _ _ rfl rfl rfl rfl w hw
  refine ⟨FreeGroup.lift g, ?_, ?_⟩
  · rw [injective_iff_map_eq_one]
    intro w hw
    by_contra hne
    exact lift_ne_one g mat (mat (g 0)) (mat (g 0))⁻¹ (mat (g 1)) (mat (g 1))⁻¹
      hmatinj rfl rfl rfl rfl hword w hne hw
  · intro w hw
    refine ⟨lift_det_one g mat hmatdet hdetA hdetB w, ?_⟩
    have h := lift_ne_one g mat (mat (g 0)) (mat (g 0))⁻¹ (mat (g 1)) (mat (g 1))⁻¹
      hmatinj rfl rfl rfl rfl hword w hw
    intro hc; exact h (by rw [hc]; rfl)


end Problems.Geometry.banach_tarski
