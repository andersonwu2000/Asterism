<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For a leaf `a ^ n % k = c` with large `n`, try `by rw [Nat.pow_mod]` alone — it reduces the base mod `k` and the kernel finishes by `rfl` via Mathlib's `Nat.powMod` (LSP ~60-90s but 0 diagnostics), avoiding the manual cyclic `base^2 % k = 1` decomposition.
- For `(a^m + b^n) % k = c` with large powers, plain `decide` times out the gateway and `native_decide` is rejected for rogue axioms — decompose via `Nat.add_mod` into per-power sub-claims and let cyclic structure (`Nat.pow_mod` + `base^2 % k = 1`) handle each piece.
