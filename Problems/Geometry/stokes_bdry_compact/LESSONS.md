<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `ModelWithCorners.isClosed_boundary` fails to synthesize `[IsManifold (𝓡∂ (n+1)) ?s M]` when a local `n : ℕ` (dimension) shadows the section's `{n : WithTop ℕ∞}` (smoothness); fix by providing `(n := (∞ : WithTop ℕ∞))` explicitly plus `(by exact_mod_cast ENat.top_ne_zero)` for the `hn` side-condition.
