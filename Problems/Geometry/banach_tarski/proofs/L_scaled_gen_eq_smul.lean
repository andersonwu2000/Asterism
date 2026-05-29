import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- scaled_gen_eq_smul: each scaled generator equals (1/3) • its un-normalized literal,
-- proved by casework on all four (Fin 2 × Bool) combinations using hA/hAInv/hB/hBInv.
theorem scaled_gen_eq_smul (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1 / 3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1 / 3 : ℝ) • !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hB : B = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hBInv : BInv = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]) :
    ∀ x : Fin 2 × Bool,
      (if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv))
        = (1 / 3 : ℝ) •
          (if x.1 = 0 then
            (if x.2 then !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3]
                    else !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
          else
            (if x.2 then !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]
                    else !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])) := by
  intro ⟨i, b⟩
  fin_cases i <;> fin_cases b <;> simp [hA, hAInv, hB, hBInv]

end Problems.Geometry.banach_tarski

