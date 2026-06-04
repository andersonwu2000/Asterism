import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_exists_smaller_triple

namespace Problems.sylvester_gallai

-- By contradiction: if s ∈ P with Collinear p q s, s ≠ p, s ≠ q, then we can produce
-- a strictly closer triple in P³, contradicting the minimality hmin.
-- Sub-goal: given a third collinear P-point off {p,q}, exhibit a strict-smaller-D triple.
theorem s10207 : ∀ (P : Finset (ℝ × ℝ)) (p : ℝ × ℝ), p ∈ P →
    ∀ (q : ℝ × ℝ), q ∈ P → ∀ (r : ℝ × ℝ), r ∈ P → p ≠ q → ¬ Collinear p q r →
    (∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
      ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
          / ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
      ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1))^2
          / ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2)) →
    ∀ s ∈ P, Collinear p q s → s = p ∨ s = q  := by
  intro P p hp q hq r hr hpq hnc hmin s hs hcoll
  by_contra hne
  push_neg at hne
  obtain ⟨hsp, hsq⟩ := hne
  have hsmaller := exists_smaller_triple P p hp q hq r hr hpq hnc hmin s hs hcoll hsp hsq
  obtain ⟨p', hp', q', hq', r', hr', hpq', hnc', hlt⟩ := hsmaller
  have hle := hmin p' hp' q' hq' r' hr' hpq' hnc'
  linarith

end Problems.sylvester_gallai
