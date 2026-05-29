import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- smul_mulvec_middle: extract middle component from scaled mulVec identity;
-- uses Matrix.smul_mulVec to commute scalar, then congr_fun at index 1.
-- entry_kind: Builder

theorem smul_mulvec_middle (c : ℝ) (p q r : ℤ) (U : Matrix (Fin 3) (Fin 3) ℝ)
    (hU : U.mulVec ![0, 1, 0] = ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2])
    (h1 : (c • U).mulVec ![0, 1, 0] = ![0, 1, 0]) :
    c * (q : ℝ) = 1 := by
  have hsmul : c • U.mulVec ![0, 1, 0] = ![0, 1, 0] := by
    rw [← Matrix.smul_mulVec]; exact h1
  rw [hU] at hsmul
  have h2 := congr_fun hsmul 1
  simp [smul_eq_mul] at h2
  exact h2


end Problems.Geometry.banach_tarski
