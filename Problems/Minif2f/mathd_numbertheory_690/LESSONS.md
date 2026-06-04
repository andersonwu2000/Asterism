<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Lower-bound on `{a | a ≡ 2 [MOD 3] ∧ a ≡ 4 [MOD 5] ∧ a ≡ 6 [MOD 7] ∧ a ≡ 8 [MOD 9]}`: `omega` does not see `Nat.ModEq` directly — `unfold Nat.ModEq at h3 h5 h7 h9` first, then `omega` closes via the lcm 315 (and 5×decide handles membership).
