<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `Nat.lcm`/`gcd` algebra, rewrite `m = (m/d)*d` and `l = (l/d)*d` then apply `Nat.lcm_mul_right` to reduce to the coprime case, closed by `Nat.coprime_div_gcd_div_gcd` + `Nat.Coprime.lcm_eq_mul`.
