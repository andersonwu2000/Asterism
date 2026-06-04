<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `Rat.num_div_den q : ↑q.num / ↑q.den = q` is the key bridge for denominator goals; combine with `Nat.cast_one` + `div_one` to handle `q.den = 1` cases cleanly.
