<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For h₁ : ∀ x, x^2 + a*x + b = (x-a)*(x-b), specialize at concrete x (e.g. `h₁ 0` → b = a*b; `h₁ 1` → 1+a+b = (1-a)(1-b)) to extract coefficient equations — much simpler than `Polynomial.coeff`-style comparison.
