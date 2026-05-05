import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s67_sub_1
import Problems.sylvester_gallai.proofs.L_s67_sub_2

namespace Problems.sylvester_gallai

theorem s67 (a b x z p : ℝ × ℝ) :
    Collinear a b x →
    Collinear a b z →
    x.2 ≠ z.2 →
    Collinear x p z →
    Collinear a b p  := by
  simp only [Collinear]
  intro h_abx h_abz h_x2z2 h_xpz
  have hs1 : (x.2 - z.2) * ((a.1 - p.1) * (b.2 - p.2) - (a.2 - p.2) * (b.1 - p.1)) = 0 :=
    s67_sub_1 a b x z p h_abx h_abz h_xpz
  exact s67_sub_2 a b x z p h_x2z2 hs1

end Problems.sylvester_gallai
