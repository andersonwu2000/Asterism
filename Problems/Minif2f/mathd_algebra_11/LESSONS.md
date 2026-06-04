<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- After `rw [ha]` for `ha : a = k * b` (k ≠ 1) followed by `field_simp`, the goal usually reduces to a `b * b⁻¹` form needing `b ≠ 0`; derive it from the parent's `a ≠ b` via `intro hbz; apply h₀; rw [ha, hbz]; ring` before `field_simp`, otherwise `ring` fails on `b * b⁻¹ * c = c`.
- For a hypothesis of shape `(num)/(denom) = c` with non-trivial `denom`, prefer `rw [div_eq_iff h_ne] at h` over `field_simp at h` — field_simp can leave the division intact (seen on `(4*a+3*b)/(a-2*b)=5`), while `div_eq_iff` cleanly yields `num = c * denom`.
