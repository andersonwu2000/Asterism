import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s83_sub_1
import Problems.sylvester_gallai.proofs.L_s83_sub_2
import Problems.sylvester_gallai.proofs.L_s83_sub_3
import Problems.sylvester_gallai.proofs.L_s83_sub_4

namespace Problems.sylvester_gallai

theorem s83 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
        ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
          ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
            ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P h_noncol h_skolem p hp q hq r hr p_ne_q hncol s hs h_col_pqs s_ne_p s_ne_q
  have h_pigeon :=
    s83_sub_1 P h_noncol h_skolem p hp q hq r hr p_ne_q hncol s hs h_col_pqs s_ne_p s_ne_q
  rcases h_pigeon with h_pq | h_ps | h_qs
  · exact s83_sub_2 P h_noncol h_skolem p hp q hq r hr p_ne_q hncol s hs h_col_pqs s_ne_p s_ne_q h_pq
  · exact s83_sub_3 P h_noncol h_skolem p hp q hq r hr p_ne_q hncol s hs h_col_pqs s_ne_p s_ne_q h_ps
  · exact s83_sub_4 P h_noncol h_skolem p hp q hq r hr p_ne_q hncol s hs h_col_pqs s_ne_p s_ne_q h_qs

end Problems.sylvester_gallai
