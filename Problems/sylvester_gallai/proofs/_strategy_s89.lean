import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s89_sub_1
import Problems.sylvester_gallai.proofs.L_s89_sub_2
import Problems.sylvester_gallai.proofs.L_s89_sub_3

namespace Problems.sylvester_gallai

theorem s89 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
        ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
          ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
            ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hexists hLine p hpP q hqP r hrP hpq hncol s hsP hsCol hsp hsq hsign hpcloser
  refine ⟨s, hsP, r, hrP, p, hpP, ?_, ?_, ?_⟩
  · exact s89_sub_1 P hexists hLine p hpP q hqP r hrP hpq hncol s hsP hsCol hsp hsq hsign hpcloser
  · exact s89_sub_2 P hexists hLine p hpP q hqP r hrP hpq hncol s hsP hsCol hsp hsq hsign hpcloser
  · exact s89_sub_3 P hexists hLine p hpP q hqP r hrP hpq hncol s hsP hsCol hsp hsq hsign hpcloser

end Problems.sylvester_gallai
