<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To witness `∃ k : ℕ, f a = a + 1987 * k` from a modular fact, the sub-goal shape `∃ a < 1987, f a % 1987 = a` (NOT `f a % 1987 = a % 1987`) is what `Nat.div_add_mod (f a) 1987 + omega` closes mechanically with `k = f a / 1987` — sidesteps the `f a ≥ a` obligation that the residue-only form leaves dangling.
- The shift identity `f(n+1987) = f n + 1987` is derived from `hff (f n)` (i.e. `f(f(f n)) = f n + 1987`) rewritten by `hff n`; this is the seed for any `iter_shift`/residue argument and is not visible from the goal statement alone.
