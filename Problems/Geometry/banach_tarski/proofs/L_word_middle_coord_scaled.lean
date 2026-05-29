import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Backward
theorem word_middle_coord_scaled
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1 / 3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1 / 3 : ℝ) • !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hB : B = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hBInv : BInv = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    ∃ q : ℤ, ¬ (3 ∣ q) ∧ 1 ≤ (FreeGroup.toWord w).length ∧
      (Matrix.mulVec
        (((FreeGroup.toWord w).map
            (fun x : Fin 2 × Bool =>
              if x.1 = 0 then (if x.2 then A else AInv)
                         else (if x.2 then B else BInv))).prod)
        ![0, 1, 0]) 1
      = ((1 : ℝ) / 3) ^ (FreeGroup.toWord w).length * (q : ℝ) := by sorry

end Problems.Geometry.banach_tarski
