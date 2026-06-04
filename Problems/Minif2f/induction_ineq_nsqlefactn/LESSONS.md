<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- The `n !` factorial notation is `scoped` in namespace `Nat`; `open Nat` from Defs.lean does NOT propagate to patch.lean, so prepend `open Nat in` (or `open Nat`) before any theorem mentioning `n !` or the signature fails to parse with "unexpected token ':='; expected no space before or term".
