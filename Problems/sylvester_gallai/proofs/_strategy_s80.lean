import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s80_sub_1

namespace Problems.sylvester_gallai

theorem s80 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      (∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r ∧
        ∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
          ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
            ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2)) →
      False  := by
  intro P h_noncol h_skolem h_ex
  obtain ⟨p, hp, q, hq, r, hr, hpq, hpqr, h_min⟩ := h_ex
  obtain ⟨p', hp', q', hq', r', hr', hp'q', hp'q'r', h_lt⟩ :=
    s80_sub_1 P h_noncol h_skolem p hp q hq r hr hpq hpqr
  exact absurd (h_min p' hp' q' hq' r' hr' hp'q' hp'q'r') (not_le.mpr h_lt)

end Problems.sylvester_gallai
