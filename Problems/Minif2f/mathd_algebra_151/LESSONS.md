<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Simpler alternative for `⌈√n⌉ = k`: establish `Real.sqrt n ^ 2 = n` via `Real.sq_sqrt (by norm_num)` and `0 ≤ Real.sqrt n` via `Real.sqrt_nonneg`, bound with `nlinarith`, convert via `Int.lt_ceil.mpr` / `Int.ceil_le.mpr` + `exact_mod_cast`, then close with `omega` — avoids `Real.sqrt_sq` rewrites and `floor_eq_iff` casting.
- For `⌊sqrt n⌋ = k` (or `⌈sqrt n⌉`): rewrite the integer bound as `Real.sqrt (k^2)` via `Real.sqrt_sq (by norm_num)`, apply `Real.sqrt_le_sqrt` / `Real.sqrt_lt_sqrt`, then close with `Int.floor_eq_iff` + `exact_mod_cast` / `push_cast; linarith`.
