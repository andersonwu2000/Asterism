<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Root `f 8 = 19` is a minif2f transcription bug — actual value is `3·√9 − 8 = 1`; after `rw [h₀]` and `Real.sqrt_sq` on `9 = 3^2`, `norm_num` reduces the goal to `False`, so any descendant goal that asserts `f 8 = 19` is unprovable and should decline.
