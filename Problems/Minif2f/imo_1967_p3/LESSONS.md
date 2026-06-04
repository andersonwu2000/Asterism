<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `∏ i ∈ Finset.Icc 1 n, c (m + i) - c k` parses as `(∏ c(m+i)) - c k` (product minus single term), NOT `∏ (c(m+i) - c k)`; verify with `show` before building any sub-goal strategy around this expression.
