import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- segment_const_deriv: deriv of straight-line segment γ(s)=z+s·h equals h
theorem segment_const_deriv (z h : ℂ) (t : ℝ) :
    deriv (fun s : ℝ => z + (s:ℂ) * h) t = h := by
  have hd : HasDerivAt (fun s : ℝ => z + (s : ℂ) * h) h t := by
    have h2 : HasDerivAt (fun s : ℝ => (s : ℂ) * h) (1 * h) t :=
      (Complex.ofRealCLM.hasDerivAt (x := t)).mul_const h
    simpa using h2.const_add z
  exact hd.deriv

end Problems.residue_thm
