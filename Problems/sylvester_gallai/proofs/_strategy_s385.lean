import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_perp_descent_cross_mult
import Problems.sylvester_gallai.proofs.L_line_dir_sq_pos
import Problems.sylvester_gallai.proofs.L_on_line_pt_to_off_sq_pos

namespace Problems.sylvester_gallai

-- Clear denominators via `div_lt_div_iff₀`: split the strict-descent ratio
-- inequality into (i) positivity of the two denominators and (ii) the
-- cross-multiplied polynomial inequality. Each piece is strictly simpler:
-- (i) is pure non-degeneracy from `¬ Collinear a b c` (with `Collinear a b v`
-- giving `v ≠ c` for the second denominator); (ii) is a division-free
-- polynomial inequality, the genuine algebraic core, which becomes amenable
-- to parametrising `u, v` along line `ab` and cancelling denominators.
theorem s385 :
    ∀ a b u v c : ℝ × ℝ,
      u ≠ v → Collinear a b u → Collinear a b v → ¬ Collinear a b c →
      ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) *
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)) ≥ 0 →
      ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2))^2 ≤
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 →
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1))^2 /
        ((v.1 - c.1)^2 + (v.2 - c.2)^2) <
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
        ((b.1 - a.1)^2 + (b.2 - a.2)^2)  := by
  intro a b u v c huv hu hv hc hsign hsq
  have h_denom_ab :
      (b.1 - a.1)^2 + (b.2 - a.2)^2 > 0 :=
    line_dir_sq_pos a b c hc
  have h_denom_vc :
      (v.1 - c.1)^2 + (v.2 - c.2)^2 > 0 :=
    on_line_pt_to_off_sq_pos a b v c hc hv
  have h_cross_mult :
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1))^2 *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) <
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 *
          ((v.1 - c.1)^2 + (v.2 - c.2)^2) :=
    kelly_perp_descent_cross_mult a b u v c huv hu hv hc hsign hsq
  rw [div_lt_div_iff₀ h_denom_vc h_denom_ab]
  exact h_cross_mult

end Problems.sylvester_gallai
