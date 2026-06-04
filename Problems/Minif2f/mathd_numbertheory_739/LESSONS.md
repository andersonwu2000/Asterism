<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `9!` factorial notation needs `open Nat` in patch.lean — Defs.lean's `open Nat` does not propagate through imports, so without it the parser reads `9` then chokes on `!`; add `open Nat` (or write `Nat.factorial 9`) before any tactic touches the goal.
