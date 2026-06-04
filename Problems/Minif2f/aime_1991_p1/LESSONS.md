<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For ℕ Diophantine goals with `x*y + (x+y) = c` style hypotheses, `nlinarith` derives tight `x,y ≤ c/2` bounds, then `interval_cases x <;> interval_cases y <;> omega` brute-forces (omega evaluates h₂ numerically once x,y are constants — no need to factor `x²y+xy² = xy(x+y)`).
