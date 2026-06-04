<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `native_decide` ships a `_native.native_decide.ax_*` axiom that leaf-bypass rejects as rogue; for large modular-exponent goals use `Nat.pow_mod` + `pow_mul` to split into a small kernel-`decide`able step plus `one_pow`/`rfl`.
