<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Source bug: `a b c : ℕ` makes `1/a`, `1/b`, `1/c`, `1/36` ℕ-division (all `=0` for ≥2), so `h₂` collapses to `1=1` and `b=3` is false — counterexample `a=b=c=2, n=2` is kernel-checkable via `norm_num`; decline as `unprovable`.
