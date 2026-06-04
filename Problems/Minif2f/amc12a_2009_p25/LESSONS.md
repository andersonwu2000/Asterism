<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For all denominator `≠ 0` goals in this recurrence (positive or negative, with or without `1/√3` fractions), the uniform pattern `intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]` closes them; `positivity`, `ne_of_lt`, and pre-proved equalities are unnecessary.
- For full 24-step recurrence chains (base_25/base_26), `set_option maxHeartbeats 800000` is insufficient — use 2000000; the `linter.style.maxHeartbeats` linter also requires the explanatory comment to appear immediately AFTER `set_option maxHeartbeats 2000000 in` (between it and the `theorem` line), not before, or a style warning fires.
- Long step-chain proofs (20+ recurrence steps, e.g. base_25/base_26) require `set_option maxHeartbeats 800000 in` immediately before the theorem; the default 200 000 budget is exhausted by the accumulated `field_simp`/`nlinarith` calls and the LSP validator reports a whnf timeout masking which step actually failed.
- When a recurrence denominator is negative (e.g., `1 - 1/√3*(2+√3) < 0`), prove `hd : expr ≠ 0` via `have h : expr = simplified_neg_form := by field_simp [sqrt3_ne]` + `have hlt : expr < 0 := by linarith [div_pos ...]` + `exact ne_of_lt hlt`; `positivity` and `nlinarith` alone fail on negative-valued denominators.
- When `field_simp` leaves residual fractions in a recurrence-step goal, pre-prove the complex denominator equals a simple form (e.g., `1 - (-1/√3)*((√3-1)/(√3+1)) = 2/√3`) via `field_simp [hs_ne, hs1]; nlinarith [hs2]`, then `rw` that result before the outer `field_simp` to force full denominator clearance.
- For recurrence steps involving `1/√3` denominators, the pattern `rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [Real.mul_self_sqrt (show (3:ℝ) ≥ 0 from by norm_num)]` closes polynomial √3 goals; show `hd` via `positivity` when the denominator contains `1/√3`, otherwise `nlinarith [hsq3_sq]`.
