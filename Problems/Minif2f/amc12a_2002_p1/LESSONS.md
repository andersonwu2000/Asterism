<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Avoid generic sub-goal slugs like `factorization` — they shadow-clash with Mathlib root-scope names (e.g. `UniqueFactorizationMonoid.factorization` accepts a ℂ→ℂ arg) and `(slug f) h₀` resolves to the wrong global; prefer descriptive slugs like `roots_iff_neg_three_halves_or_five`.
