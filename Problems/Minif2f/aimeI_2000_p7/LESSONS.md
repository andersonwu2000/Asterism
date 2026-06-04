<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Final closer `↑m.den + m.num = 5` after rewriting `m = 1/4`: `decide`/`rfl` get stuck on `(1/4 : ℚ).den`/`.num` reduction past the ℤ-coercion; `native_decide` closes it (style warning only) — or rewrite via `Rat.num_div`/`Rat.den_div` lemmas before a clean `decide`.
