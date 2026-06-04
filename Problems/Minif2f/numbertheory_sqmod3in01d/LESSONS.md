<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When proving `n ∣ polynomial(a)` after `obtain ⟨k, hk⟩ : n ∣ a - s`, close the witness equality with `linear_combination c * hk` (not `nlinarith`/`linarith`) — `linear_combination` dispatches via `ring` and handles nonlinear polynomial identities in ℤ cleanly.
- For `a % 3 = k` goals: derive `a = 3*(a/3) + k` via `Int.emod_add_mul_ediv` + `omega`, then use `obtain ⟨k, hk⟩ : ∃ k, a = 3*k + r := ⟨a/3, key⟩` before `rw [hk]; ring` — direct `rw [key]` also rewrites `a/3` inside the goal, breaking `ring`.
