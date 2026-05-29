import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct leaf computation: each of the 4 generator matrices acting on the
-- integer-lattice vector (p√2, q, r√2) yields the claimed integer recursion.
-- Split the conjunction, then per matrix entry: unfold mulVec, ring_nf to
-- collect the lone √2² term, rewrite √2²=2 (hpow), close by ring. No
-- sub-goals — leaf-bypass.
theorem s11392 (p q r : ℤ) :
    Matrix.mulVec !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3]
        ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2]
      = ![((p - 2 * q : ℤ) : ℝ) * Real.sqrt 2, ((4 * p + q : ℤ) : ℝ),
          ((3 * r : ℤ) : ℝ) * Real.sqrt 2]
    ∧ Matrix.mulVec !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3]
        ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2]
      = ![((p + 2 * q : ℤ) : ℝ) * Real.sqrt 2, ((-4 * p + q : ℤ) : ℝ),
          ((3 * r : ℤ) : ℝ) * Real.sqrt 2]
    ∧ Matrix.mulVec !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]
        ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2]
      = ![((3 * p : ℤ) : ℝ) * Real.sqrt 2, ((q - 4 * r : ℤ) : ℝ),
          ((2 * q + r : ℤ) : ℝ) * Real.sqrt 2]
    ∧ Matrix.mulVec !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]
        ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2]
      = ![((3 * p : ℤ) : ℝ) * Real.sqrt 2, ((q + 4 * r : ℤ) : ℝ),
          ((-2 * q + r : ℤ) : ℝ) * Real.sqrt 2]
    := by
  have hpow : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  refine ⟨?_, ?_, ?_, ?_⟩ <;>
    (funext i
     fin_cases i <;>
       simp [Matrix.mulVec, Matrix.cons_val_zero, Matrix.cons_val_one,
         Matrix.head_cons] <;>
       ring_nf <;>
       simp only [hpow] <;>
       ring)






end Problems.Geometry.banach_tarski
