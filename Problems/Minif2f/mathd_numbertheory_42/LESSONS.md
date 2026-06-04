<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To pin an `IsLeast S u` value when `S = {a | 0 < a ∧ 27*a % 40 = 17}`: witness a concrete element (e.g. `(h₀ 11).mpr (by norm_num)`) to bound u, then `interval_cases u <;> omega` — omega discharges the modular condition at each concrete candidate, ruling out all but the true minimum.
