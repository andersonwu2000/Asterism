<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For bounded-range integer divisibility goals (e.g. `m ∣ 215` with `10 ≤ m ≤ 99 → m = 43`), `interval_cases m <;> omega` suffices: `omega` handles both the false-divisor contradictions and the trivial equality for the true divisor.
