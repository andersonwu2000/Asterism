<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `native_decide` is rejected by leaf-bypass axiom check (emits `_native.native_decide.ax_*` rogue axioms) despite compiling; for `Nat.sqrt` goals use `set k := Nat.sqrt _`, bound `k` via `k*k = n` and `Nat.mul_le_mul`, then `interval_cases k <;> omega`.
