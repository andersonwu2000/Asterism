<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- The `n!` factorial notation is scoped under `Nat`; patch.lean must insert `open Nat` between the `namespace` and `theorem` lines (signature text unchanged, no `patch_signature_mismatch`) — otherwise the skeleton fails to parse with `unexpected token '!'`, and `decide` then closes `7! % 23 = 3` immediately.
