<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `Nat.dvd_sub'` is NOT a constant in this toolchain; use `Nat.dvd_sub : k ∣ m → k ∣ n → k ∣ m - n` (2-arg, no `n ≤ m` premise — it IS the unordered version here).
