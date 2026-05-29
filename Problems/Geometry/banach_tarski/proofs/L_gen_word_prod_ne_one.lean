import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- gen_word_prod_ne_one: transports matrix-level non-identity (hword) to isometry-product ≠ 1
-- via map_list_prod; bridges mat((g i)⁻¹) = AInv/BInv using Matrix.inv_eq_right_inv
-- applied to the right-inverse identity mat(g i) * mat((g i)⁻¹) = 1 from map_mul + map_one.
-- entry_kind: Builder
theorem gen_word_prod_ne_one

    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hinj : Function.Injective mat)
    (hg0 : mat (g 0) = A) (hg0inv : (mat (g 0))⁻¹ = AInv)
    (hg1 : mat (g 1) = B) (hg1inv : (mat (g 1))⁻¹ = BInv)
    (hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then A else AInv)
                    else (if x.2 then B else BInv))).prod ≠ 1) :
    ∀ v : FreeGroup (Fin 2), FreeGroup.toWord v ≠ [] →
      ((FreeGroup.toWord v).map (fun x : Fin 2 × Bool =>
        if x.2 then g x.1 else (g x.1)⁻¹)).prod ≠ 1 := by

  intro v hv
  have hv1 : v ≠ 1 := fun h => hv (FreeGroup.toWord_eq_nil_iff.mpr h)
  intro hcontra
  apply hword v hv1
  have mat_inv_g0 : mat ((g 0)⁻¹) = AInv := by
    have h : mat (g 0) * mat ((g 0)⁻¹) = 1 := by
      rw [← map_mul, mul_inv_cancel, map_one]
    rw [← hg0inv]; exact (Matrix.inv_eq_right_inv h).symm
  have mat_inv_g1 : mat ((g 1)⁻¹) = BInv := by
    have h : mat (g 1) * mat ((g 1)⁻¹) = 1 := by
      rw [← map_mul, mul_inv_cancel, map_one]
    rw [← hg1inv]; exact (Matrix.inv_eq_right_inv h).symm
  have key : ∀ x : Fin 2 × Bool,
      mat (if x.2 then g x.1 else (g x.1)⁻¹) =
      if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv) := by
    intro ⟨i, b⟩
    fin_cases i <;> fin_cases b <;>
      simp only [Fin.zero_eta, Fin.reduceEq, ↓reduceIte, Fin.mk_one, Bool.false_eq_true]
    · exact hg0
    · exact mat_inv_g0
    · exact hg1
    · exact mat_inv_g1


  have hbridge : mat ((FreeGroup.toWord v).map
      (fun x : Fin 2 × Bool => if x.2 then g x.1 else (g x.1)⁻¹)).prod =
      ((FreeGroup.toWord v).map (fun x : Fin 2 × Bool =>
      if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv))).prod := by
    rw [map_list_prod, List.map_map]
    congr 1
    apply List.map_congr_left
    intro x _
    exact key x
  rw [← hbridge, hcontra, map_one]


end Problems.Geometry.banach_tarski
