import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s6_sub_1
import Problems.sylvester_gallai.proofs.L_s6_sub_2

namespace Problems.sylvester_gallai

theorem s6 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q  := by
  intro P hP
  obtain ⟨p, hp, a, ha, b, hb, hab, hnc, hmin⟩ := s6_sub_1 P hP
  exact ⟨a, ha, b, hb, hab, s6_sub_2 P p a b hp ha hb hab hnc hmin⟩

end Problems.sylvester_gallai
