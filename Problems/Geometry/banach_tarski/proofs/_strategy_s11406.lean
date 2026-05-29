import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_scaled_eq_one_imp_dvd
import Problems.Geometry.banach_tarski.proofs.L_word_middle_coord_scaled

namespace Problems.Geometry.banach_tarski

-- Freeness assembly: a reduced nonempty word in the orthogonal generators cannot be 1.
-- Two sub-goals combine: `word_middle_coord_scaled` realizes the word-product on ![0,1,0]
-- whose middle coordinate is (1/3)^n · q with ¬3∣q and n = (toWord w).length ≥ 1 (this
-- absorbs the (1/3)^n smul-scaling bridge from normalized to un-normalized generators and
-- the cited s11396 residue invariant). Assuming the product = 1 forces that coordinate to
-- equal 1, so 1 = (1/3)^n · q; `scaled_eq_one_imp_dvd` turns this into 3∣q for n ≥ 1,
-- contradicting ¬3∣q. Both sub-goals are strictly smaller: one a realization/scaling
-- transport, the other a self-contained real→ℤ divisibility arithmetic.
theorem s11406
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
  intro hone
  obtain ⟨q, hq, hn, hcoord⟩ :=
    word_middle_coord_scaled A AInv B BInv hA hAInv hB hBInv w hw
  rw [hone, Matrix.one_mulVec] at hcoord
  exact hq (scaled_eq_one_imp_dvd (FreeGroup.toWord w).length q hn (by simpa using hcoord))

end Problems.Geometry.banach_tarski
