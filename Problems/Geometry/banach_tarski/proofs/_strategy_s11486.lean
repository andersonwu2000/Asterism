import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_freegroup_lift_injective_of_word_prod_ne_one
import Problems.Geometry.banach_tarski.proofs.L_gen_word_prod_ne_one

namespace Problems.Geometry.banach_tarski

-- Reduce `lift g w ≠ 1` to injectivity of `lift g`: sibling
-- `freegroup_lift_injective_of_word_prod_ne_one` (s11411) gives `Injective (lift g)` from a
-- per-word G-product-≠-1 hypothesis, so `lift g w = 1 = lift g 1` would force `w = 1`.
-- The one sub-goal `gen_word_prod_ne_one` transports `hword`'s matrix-product fact to the
-- needed G-product fact through the injective monoid hom `mat`.
theorem s11486
    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hinj : Function.Injective mat)
    (hg0 : mat (g 0) = A) (hg0inv : (mat (g 0))⁻¹ = AInv)
    (hg1 : mat (g 1) = B) (hg1inv : (mat (g 1))⁻¹ = BInv)
    (hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then A else AInv)
                    else (if x.2 then B else BInv))).prod ≠ 1)
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    FreeGroup.lift g w ≠ 1  := by
  have hgprod := gen_word_prod_ne_one g mat A AInv B BInv hinj hg0 hg0inv hg1 hg1inv hword
  have hinjlift : Function.Injective (FreeGroup.lift g) :=
    freegroup_lift_injective_of_word_prod_ne_one g hgprod
  intro hc
  exact hw (hinjlift (by rw [hc, map_one]))

end Problems.Geometry.banach_tarski
