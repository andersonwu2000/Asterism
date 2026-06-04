import Mathlib

namespace Problems.Minif2f.imo_1993_p5

-- wythoff_one: numerical check f(1)=2 via sqrt(5) bounds + Int.floor_eq_iff
theorem wythoff_one :
    (fun n : ℕ => (⌊((n : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋).toNat - 1) 1 = 2 := by
  norm_num
  rw [show (2 : ℝ) * ((1 + Real.sqrt 5) / 2) = 1 + Real.sqrt 5 from by ring]
  have hsq : Real.sqrt 5 ^ 2 = 5 := Real.sq_sqrt (by norm_num)
  have hnn : (0 : ℝ) ≤ Real.sqrt 5 := Real.sqrt_nonneg 5
  have h1 : (2 : ℝ) < Real.sqrt 5 := by nlinarith
  have h2 : Real.sqrt 5 < 3 := by nlinarith
  rw [show (⌊(1 + Real.sqrt 5)⌋ : ℤ) = 3 from ?_]
  · rfl
  · rw [Int.floor_eq_iff]
    constructor <;> push_cast <;> linarith

end Problems.Minif2f.imo_1993_p5
