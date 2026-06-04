<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `Real.rpow` exponent injectivity (`a^x = a^y → x = y` with `a > 1`), use `(Real.strictMono_rpow_of_base_gt_one h).injective`; `Real.rpow_left_injective` does NOT exist (only the ℝ≥0/ℝ≥0∞ versions do).
