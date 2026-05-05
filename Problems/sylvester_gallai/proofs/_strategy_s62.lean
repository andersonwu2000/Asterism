import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s62_sub_1
import Problems.sylvester_gallai.proofs.L_s62_sub_2
import Problems.sylvester_gallai.proofs.L_s62_sub_3

namespace Problems.sylvester_gallai

theorem s62 (p a b x z : ℝ × ℝ) :
    ¬ Collinear p a b →
    a ≠ b →
    Collinear a b x →
    Collinear a b z →
    x ≠ z →
    ¬ Collinear x p z  := by
  intro h_nc _ h_cx h_cz h_xz h_xpz
  have hcases : x.1 ≠ z.1 ∨ x.2 ≠ z.2 := by
    by_contra h
    push_neg at h
    exact h_xz (Prod.ext h.1 h.2)
  rcases hcases with h1 | h2
  · exact h_nc (s62_sub_3 a b p (s62_sub_1 a b x z p h_cx h_cz h1 h_xpz))
  · exact h_nc (s62_sub_3 a b p (s62_sub_2 a b x z p h_cx h_cz h2 h_xpz))

end Problems.sylvester_gallai
