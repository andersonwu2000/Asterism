import Mathlib
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_phi_floor_lt

namespace Problems.Minif2f.imo_1993_p5

-- Reduce F·φ < F + k + 1 (F = ⌊(k+1)·φ⌋) to the strict floor inequality
-- F < (k+1)·φ via irrationality of (k+1)·φ for k+1 ≥ 1.
-- Combinator: multiply (φ-1)>0 by ((k+1)·φ - F)>0 to get (k+1)·(φ²-φ) - F·(φ-1) > 0,
-- then nlinarith with √5·√5 = 5 closes since φ²-φ = 1.
theorem s9953 :
    ∀ k : ℕ,
      (⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℝ)
            * ((1 + Real.sqrt 5) / 2)
        < ((⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℤ) : ℝ) + (k : ℝ) + 1  := by
  intro k
  have h_strict := wythoff_phi_floor_lt k
  have h_sqrt5 : Real.sqrt 5 * Real.sqrt 5 = 5 :=
    Real.mul_self_sqrt (by norm_num : (0:ℝ) ≤ 5)
  have h_sqrt5_gt_one : (1 : ℝ) < Real.sqrt 5 := by
    nlinarith [h_sqrt5, Real.sqrt_nonneg (5 : ℝ)]
  have h_phi_sub_pos : (0 : ℝ) < (1 + Real.sqrt 5) / 2 - 1 := by linarith
  have h_diff_pos : (0 : ℝ) <
      ((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)
        - ((⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℤ) : ℝ) := by linarith
  have key := mul_pos h_phi_sub_pos h_diff_pos
  nlinarith [key, h_sqrt5]

end Problems.Minif2f.imo_1993_p5
