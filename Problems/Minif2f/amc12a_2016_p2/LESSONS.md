<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For goals needing injectivity of `(b : ℝ) ^ · : ℝ → ℝ`, `Real.rpow_left_strictMono` and `Real.rpow_left_injective` do not exist; build `StrictMono` via `fun a b hab => Real.rpow_lt_rpow_of_exponent_lt (by norm_num : 1 < b) hab`, then use `.injective`.
- For `rpow` power-consolidation goals, use `norm_num` to rewrite `(100:ℝ) = (10:ℝ)^(2:ℝ)` (rpow form), then `← Real.rpow_mul (by norm_num : 0 ≤ 10)` and `← Real.rpow_add (by norm_num : 0 < 10)`; `rpow_natCast` is a dead end here.
