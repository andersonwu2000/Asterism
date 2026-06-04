<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `native_decide` on closed Nat facts (e.g. `Nat.gcd 20! 200000 = 40000`) emits a rogue compiler axiom (`*._native.native_decide.ax_*`) that the framework's leaf-bypass axiom checker rejects; use plain `decide` instead — the Euclidean reduction is fast enough at this scale.
- The `n !` factorial notation needs `open Nat` in the patch file itself — `open Nat` in Defs.lean doesn't transit through the import, so a fresh patch parsing `20!` hits `unexpected token '!'` until you add `open Nat` above the namespace.
