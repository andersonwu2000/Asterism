<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- If the goal signature uses scoped notation (e.g. `n!` from `Nat`, `⟪·,·⟫` from inner product), patch.lean must `open Nat` / `open scoped <NS>` itself — Defs.lean's `open` does NOT propagate across imports, so lake build errors with "unexpected token" on the notation.
