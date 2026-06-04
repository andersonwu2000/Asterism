import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_min_implies_ordinary
import Problems.sylvester_gallai.proofs.L_min_perp_dist_triple

namespace Problems.sylvester_gallai

-- Kelly's proof: pick (p,q,r) ∈ P³ with p≠q, ¬Collinear p q r, minimising the
-- squared perpendicular distance from r to line pq; then (p,q) is an ordinary pair.
-- Sub-goal 1: existence of such a minimum (finite-image min over P×P×P).
-- Sub-goal 2: the geometric core — at the minimum, no third P-point lies on line pq.
theorem s10205 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q  := by
  intro P hexists
  have h_min := min_perp_dist_triple P hexists
  obtain ⟨p, hp, q, hq, r, hr, hpq, hnc, hmin⟩ := h_min
  refine ⟨p, hp, q, hq, hpq, ?_⟩
  intro s hs hcoll
  exact kelly_min_implies_ordinary P p hp q hq r hr hpq hnc hmin s hs hcoll

end Problems.sylvester_gallai
