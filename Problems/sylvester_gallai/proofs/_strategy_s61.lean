import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s61_sub_1
import Problems.sylvester_gallai.proofs.L_s61_sub_2

namespace Problems.sylvester_gallai

theorem s61 (p a b c x z : ℝ × ℝ) :
    ¬ Collinear p a b →
    Collinear a b c →
    a ≠ b →
    (x = a ∨ x = b ∨ x = c) →
    (z = a ∨ z = b ∨ z = c) →
    x ≠ z →
    ¬ Collinear x p z  := by
  intro h_npab h_abc h_ab h_x h_z h_xz
  have h_abx : Collinear a b x := s61_sub_1 a b c x h_abc h_x
  have h_abz : Collinear a b z := s61_sub_1 a b c z h_abc h_z
  exact s61_sub_2 p a b x z h_npab h_ab h_abx h_abz h_xz

end Problems.sylvester_gallai
