import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s71_sub_1
import Problems.sylvester_gallai.proofs.L_s71_sub_2
import Problems.sylvester_gallai.proofs.L_s71_sub_3

namespace Problems.sylvester_gallai

theorem s71 (a b x z p : ℝ × ℝ) :
    Collinear a b x →
    Collinear a b z →
    x.1 ≠ z.1 →
    Collinear x p z →
    Collinear a b p  := by
  intro h_abx h_abz h_ne h_xpz
  have h1 : (a.1 - b.1) * (x.2 - z.2) = (a.2 - b.2) * (x.1 - z.1) :=
    s71_sub_1 a b x z h_abx h_abz
  have h2 : (a.1 - b.1) * (p.2 - z.2) = (a.2 - b.2) * (p.1 - z.1) :=
    s71_sub_2 a b x z p h1 h_ne h_xpz
  exact s71_sub_3 a b z p h_abz h2

end Problems.sylvester_gallai
