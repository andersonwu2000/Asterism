import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s115_sub_3 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ∀ (μ : ℝ),
      s.1 - q.1 = μ * (p.1 - q.1) →
      s.2 - q.2 = μ * (p.2 - q.2) →
      (q.1 - r.1)^2 + (q.2 - r.2)^2 > 0 →
      ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 > 0 →
      2 * μ * ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) ≤ 0 →
      ((s.1 - r.1) * (q.2 - r.2) - (s.2 - r.2) * (q.1 - r.1))^2 *
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
          ((s.1 - r.1)^2 + (s.2 - r.2)^2) := by
  intro P _hP1 _hP2 p _hp q _hq r _hr _hpq _hncolr s _hs _hcollpqs _hsp _hsq
        _h1 _h2 μ hμ1 hμ2 hQr hD2pos h2μAle
  have hs1 : s.1 = q.1 + μ * (p.1 - q.1) := by linarith
  have hs2 : s.2 = q.2 + μ * (p.2 - q.2) := by linarith
  have key :
      ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
          ((s.1 - r.1)^2 + (s.2 - r.2)^2) -
        ((s.1 - r.1) * (q.2 - r.2) - (s.2 - r.2) * (q.1 - r.1))^2 *
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) =
      ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
        (((q.1 - r.1)^2 + (q.2 - r.2)^2) -
          2 * μ * ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))) := by
    rw [hs1, hs2]; ring
  have hpos :
      ((q.1 - r.1)^2 + (q.2 - r.2)^2) -
        2 * μ * ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) > 0 := by
    linarith
  have hdiff :
      ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
          ((s.1 - r.1)^2 + (s.2 - r.2)^2) -
        ((s.1 - r.1) * (q.2 - r.2) - (s.2 - r.2) * (q.1 - r.1))^2 *
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) > 0 := by
    rw [key]
    exact mul_pos hD2pos hpos
  linarith

end Problems.sylvester_gallai
