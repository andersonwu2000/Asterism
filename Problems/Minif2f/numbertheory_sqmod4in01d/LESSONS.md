<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `a^2 % n` over ℤ: `omega` can't handle the nonlinear `a^2`; chain `sq` then `Int.mul_emod` to rewrite as `((a%n)*(a%n)) % n`, then `rcases` on `a % n ∈ {0,…,n-1}` (by `omega`) and close each case with `decide` (note: `Int.pow_emod` does not exist).
