<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove `x^n % m = c` given `x % m = k`: rewrite with `Nat.pow_mod` (reduces to `(x % m)^n % m`), then `rw [hx_mod]` to substitute the known residue; the resulting concrete expression closes automatically.
- `omega` alone closes `(a + b) % n = c` from hypotheses `a % n = x` and `b % n = y` even when `a`, `b` are non-linear opaque terms (e.g. `m^2`, `2^m`) — no need to first rewrite with `Nat.add_mod`; omega abstracts the mod-bounded terms as fresh variables.
- To prove `c ≤ small + 2^2008` without evaluation: avoid `subst` (forces recursion limit); instead use `norm_num` to get `c ≤ small`, `Nat.le_add_right _ _` to extend to `small ≤ small + 2^2008`, then `omega` combines with the equality hypothesis — none of these steps evaluate the large exponent.
- To prove `p^k ∣ base^N` for large N without evaluation (e.g., `4 ∣ 2^2008`): use `Nat.pow_dvd_pow base (by norm_num : k ≤ N)` to get `base^k ∣ base^N`, then `simpa` to reduce `base^k` to its concrete value; avoids the `exponentiation.threshold 256` error that blocks `ring`/`norm_num` on large exponents.
- To prove `2^N % m = c` for large N without evaluation: establish `∀ n, 2^(4*n+r) % m = c` by induction using `pow_add` + `Nat.mul_mod` in the step, then express N as `4*k+r` via `norm_num` and instantiate; combine with `Nat.add_mod` + `omega` to close the final goal.
- `native_decide`/`decide` after `subst` on `k = 2008^2 + 2^2008` fails with `maximum recursion depth` + `exponentiation.threshold 256` warning — must decompose via mod-cycle reasoning (k % 10, k % 4, k ≥ 4) instead of brute evaluation.
