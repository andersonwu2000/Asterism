<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Root theorem is false as stated: `Real.logb` is even via `Real.log_neg_eq_log`, so hypotheses don't pin signs — counterexample `a=64, b=-8` satisfies both hypotheses but gives `a*b = -512`; decline as `unprovable`.
