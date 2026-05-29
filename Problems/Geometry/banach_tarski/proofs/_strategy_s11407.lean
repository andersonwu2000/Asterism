import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_first_letter_residue_invariant
import Problems.Geometry.banach_tarski.proofs.L_scaled_word_prod
import Problems.Geometry.banach_tarski.proofs.L_smul_mulvec_middle
import Problems.Geometry.banach_tarski.proofs.L_three_dvd_of_pow_inv_mul

namespace Problems.Geometry.banach_tarski

-- Freeness assembly: a reduced word's scaled rotation product cannot be the identity.
-- Each generator is `(1/3) • (unscaled integer matrix)`, so the word product is
-- `(1/3)^n • U` where `n = (toWord w).length ≥ 1` and `U` is the un-normalized product;
-- the proved residue invariant `s11396` gives integers `p q r` with `¬3∣q` and
-- `U.mulVec ![0,1,0] = ![p√2, q, r√2]`. If the product were `1`, the middle coordinate
-- forces `(1/3)^n * q = 1`, i.e. `q = 3^n`, divisible by 3 for `n ≥ 1` — contradicting `¬3∣q`.
-- Sub-goals: `scaled_word_prod` (factor `(1/3)^n` out of the list product, pure induction),
-- `smul_mulvec_middle` (extract the middle component of the scaled vector equation),
-- `three_dvd_of_pow_inv_mul` (the `(1/3)^n*q=1 → 3∣q` arithmetic). `s11396` is cited inline.
theorem s11407
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1/3 : ℝ) • !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hB : B = (1/3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hBInv : BInv = (1/3 : ℝ) • !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    ((FreeGroup.toWord w).map
        (fun x : Fin 2 × Bool =>
          if x.1 = 0 then (if x.2 then A else AInv)
                     else (if x.2 then B else BInv))).prod
      ≠ (1 : Matrix (Fin 3) (Fin 3) ℝ)  := by
  intro hP
  have hne : FreeGroup.toWord w ≠ [] := fun h => hw (FreeGroup.toWord_eq_nil_iff.mp h)
  set U : Matrix (Fin 3) (Fin 3) ℝ :=
    ((FreeGroup.toWord w).map
        (fun x : Fin 2 × Bool =>
          if x.1 = 0 then (if x.2 then !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3]
                                  else !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
                     else (if x.2 then !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]
                                  else !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]))).prod
    with hU_def
  obtain ⟨p, q, r, hq, -, hreal⟩ :=
    swierczkowski_first_letter_residue_invariant _ _ _ _ rfl rfl rfl rfl w hne
  rw [← hU_def] at hreal
  have hscale :=
    scaled_word_prod A AInv B BInv _ _ _ _ hA hAInv hB hBInv (FreeGroup.toWord w)
  rw [← hU_def] at hscale
  rw [hP] at hscale
  have hone : ((1/3 : ℝ) ^ (FreeGroup.toWord w).length • U).mulVec ![0, 1, 0] = ![0, 1, 0] := by
    rw [← hscale, Matrix.one_mulVec]
  have hmid := smul_mulvec_middle _ p q r U hreal hone
  have hdvd := three_dvd_of_pow_inv_mul _ q (List.length_pos_of_ne_nil hne) hmid
  exact hq hdvd

end Problems.Geometry.banach_tarski
