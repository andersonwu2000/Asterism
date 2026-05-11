import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_perp_descent_ineq
import Problems.sylvester_gallai.proofs.L_noncoll_c_v_u

namespace Problems.sylvester_gallai

-- Split the conjunction in the conclusion: non-collinearity of (c,v,u)
-- and the perpendicular-distance strict descent.
-- Each conjunct is strictly simpler — one is a pure non-degeneracy
-- (no use of `hsign`/`hsq`), the other is the geometric core
-- (algebraic inequality after clearing denominators).
theorem s384 :
    ∀ a b u v c : ℝ × ℝ,
      u ≠ v → Collinear a b u → Collinear a b v → ¬ Collinear a b c →
      ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) *
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)) ≥ 0 →
      ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2))^2 ≤
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 →
      ¬ Collinear c v u ∧
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1))^2 /
        ((v.1 - c.1)^2 + (v.2 - c.2)^2) <
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
        ((b.1 - a.1)^2 + (b.2 - a.2)^2)  := by
  intro a b u v c hne hcu hcv hcc hsign hsq
  have h1 : ¬ Collinear c v u :=
    noncoll_c_v_u a b u v c hne hcu hcv hcc
  have h2 :
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1))^2 /
          ((v.1 - c.1)^2 + (v.2 - c.2)^2) <
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) :=
    kelly_perp_descent_ineq a b u v c hne hcu hcv hcc hsign hsq
  exact ⟨h1, h2⟩

end Problems.sylvester_gallai
