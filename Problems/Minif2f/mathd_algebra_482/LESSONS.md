<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When two root equations `hm : x^2 - 12*x + k = 0` and `hn : y^2 - 12*y + k = 0` are available, `linear_combination hm - hn` closes the factored goal `(x - y) * (x + y - 12) = 0` in one step (no nlinarith/ring_nf needed).
