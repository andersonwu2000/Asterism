<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Direct sorry-free proof: factor `(n-1)·n·(n+1) - 720 = (n-9)·(n² + 9n + 80)` (nlinarith proves the factorization), then `nlinarith [sq_nonneg (2*n+9)]` shows the quadratic is positive (discriminant -239), so `mul_eq_zero` forces `n = 9`.
