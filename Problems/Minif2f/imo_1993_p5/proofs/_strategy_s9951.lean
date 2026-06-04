import Mathlib
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_phi_mul_lb
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_phi_mul_ub

namespace Problems.Minif2f.imo_1993_p5

-- Reduce ⌊⌊(k+1)·φ⌋ · φ⌋ = ⌊(k+1)·φ⌋ + k to two real-valued bounds via Int.floor_eq_iff.
-- Sub-goals:
--   wythoff_phi_mul_lb : (F : ℝ) + k ≤ F · φ        (lower bound)
--   wythoff_phi_mul_ub : F · φ < (F : ℝ) + k + 1    (strict upper bound; uses irrationality of φ)
-- Combinator: instantiate at k, push_cast + linarith to discharge each side.
theorem s9951 :
    ∀ k : ℕ,
      ⌊(⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℝ) * ((1 + Real.sqrt 5) / 2)⌋
        = ⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ + (k : ℤ)  := by
  intro k
  have h1 := wythoff_phi_mul_lb k
  have h2 := wythoff_phi_mul_ub k
  apply Int.floor_eq_iff.mpr
  refine ⟨?_, ?_⟩
  · push_cast; linarith
  · push_cast; linarith

end Problems.Minif2f.imo_1993_p5
