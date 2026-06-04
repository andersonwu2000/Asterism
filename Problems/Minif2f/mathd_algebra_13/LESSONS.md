<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When plugging in an x-value that yields a non-unit denominator (e.g. x=6 gives a/3), `norm_num` alone cannot close the goal; add `have key : n * (a / n) = a := by ring` so `linarith` can scale the equation.
