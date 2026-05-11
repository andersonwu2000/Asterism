import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_area_sq_pos
import Problems.sylvester_gallai.proofs.L_cross_eq_factor_id
import Problems.sylvester_gallai.proofs.L_dir_sq_pos
import Problems.sylvester_gallai.proofs.L_proj_sq_descent
import Problems.sylvester_gallai.proofs.L_v_lagrange_id

namespace Problems.sylvester_gallai

-- Project u, v onto the line ab in coordinates (α, β) with d := b - a; both
-- u, v share β = A/D since both lie on line ab, giving the identity
-- X · D = A · (pu - pv) (`cross_eq_factor_id`). Lagrange for v collinear gives
-- |v-c|² · D = pv² + A² (`v_lagrange_id`). Together with the abstract
-- projection-descent (pu - pv)² ≤ pv² (`proj_sq_descent` from the sign +
-- square-comparison hypotheses) and strict positivity of D (`dir_sq_pos`) and
-- A² (`area_sq_pos`), the goal X² · D < A² · |v-c|² follows: a
-- `linear_combination` produces A² · |v-c|² · D − X² · D · D = A² · (pv² +
-- A² − (pu − pv)²) ≥ A² · A² > 0, then cancel D > 0.
theorem s386 :
    ∀ a b u v c : ℝ × ℝ,
      u ≠ v → Collinear a b u → Collinear a b v → ¬ Collinear a b c →
      ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) *
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)) ≥ 0 →
      ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2))^2 ≤
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 →
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1))^2 *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) <
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 *
          ((v.1 - c.1)^2 + (v.2 - c.2)^2)  := by
  intro a b u v c huv hu hv hc hsign hsq
  have h_dir_pos : 0 < (b.1 - a.1)^2 + (b.2 - a.2)^2 := dir_sq_pos a b c hc
  have h_area_pos :
      0 < ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 :=
    area_sq_pos a b c hc
  have h_cross_id :
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1)) *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) =
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1)) *
          (((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) -
           ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))) :=
    cross_eq_factor_id a b u v c hu hv
  have h_lag :
      ((v.1 - c.1)^2 + (v.2 - c.2)^2) * ((b.1 - a.1)^2 + (b.2 - a.2)^2) =
      ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 +
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 :=
    v_lagrange_id a b v c hv
  have h_descent :
      (((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) -
       ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)))^2 ≤
      ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 :=
    proj_sq_descent _ _ hsign hsq
  have h_key :
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 *
          ((v.1 - c.1)^2 + (v.2 - c.2)^2) *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) -
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1))^2 *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) =
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 *
        (((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 +
         ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 -
         (((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) -
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)))^2) := by
    linear_combination
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 * h_lag -
      (((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1)) *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) +
       ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1)) *
          (((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) -
           ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)))) * h_cross_id
  have h_rhs_pos :
      0 < ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 *
        (((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 +
         ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 -
         (((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) -
          ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)))^2) := by
    apply mul_pos h_area_pos
    linarith [h_descent, h_area_pos]
  have h_lt_mul :
      ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1))^2 *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) <
      ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 *
          ((v.1 - c.1)^2 + (v.2 - c.2)^2) *
          ((b.1 - a.1)^2 + (b.2 - a.2)^2) := by linarith
  exact lt_of_mul_lt_mul_right h_lt_mul (le_of_lt h_dir_pos)

end Problems.sylvester_gallai
