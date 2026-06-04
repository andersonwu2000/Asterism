<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To transfer `r ∣ f(i)` to `r ∣ f(i % r)` for a polynomial `f`: establish `i ≡ i % r [MOD r]` via `simp [Nat.ModEq, Nat.mod_mod_of_dvd]`, lift through `f` using `Nat.ModEq.pow`/`.add`/`.add_right`, then use `Nat.modEq_zero_iff_dvd` in both directions to bridge divisibility through the congruence.
- In this Mathlib version `push_neg` is deprecated — use `push Not at h` instead (the deprecation message gives this fix, but avoid the warning by using `push Not` directly when pushing negation after `by_contra`).
- For ℕ divisibility goals with truncated subtraction in the dividend (e.g. `r ∣ (r-1-i)²+…`): `zify [h]` (where `h : i+1 ≤ r`) lifts to ℤ but leaves `↑(r-1-i)` unexpanded — add `have hcast : (↑(r-1-i) : ℤ) = ↑r-1-↑i := by omega` then `rw [hcast]` before `ring`; without this `rw [identity]` fails to unify.
- For quadratic arithmetic contradictions involving ℕ truncated subtraction (e.g. `i ≤ p - 2`): use `omega` to rewrite as `i + 2 ≤ p`, then `Nat.exists_eq_add_of_le` to introduce slack `d` with `p = i + 2 + d`, then `nlinarith [sq_nonneg d, mul_nonneg (Nat.zero_le d) (Nat.zero_le i)]` closes the nonlinear bound — direct `nlinarith` on ℕ subtraction fails.
- Schur's trick for IMO 1987 P6 core (`no_small_prime_factor`): given prime `r ∣ i²+i+p` with `r² ≤ i²+i+p`, the two roots of `x²+x+p ≡ 0 (mod r)` are `i` and `r-1-i`, so their minimum `k ≤ (r-1)/2` satisfies `r ∣ k²+k+p`; the degenerate case `i ≤ (r-1)/2` is ruled out by `(2i+1)² ≤ r² ≤ i²+i+p ⇒ 3i²+3i+1 ≤ p ⇒ i² < p/3`, contradicting `i > ⌊√(p/3)⌋` — pairs with a size contradiction (`Nat.Prime (k²+k+p)` from base/IH forces `r = k²+k+p ≥ p`, but `r² ≤ (p-2)²+(p-2)+p = p²-2p+2 < p²`).
- To bridge "every prime divisor of `n` equals `n`" down to "no prime divisor `r` with `r^2 ≤ n` exists", use `Nat.minFac_le_div` (contrapositive): for non-prime `n ≥ 2`, `minFac n ≤ n / minFac n`, hence `(minFac n)^2 ≤ n` — pairs with `Nat.minFac_prime`/`Nat.minFac_dvd` to instantiate the focused sub-goal on `minFac n` and conclude `Nat.Prime n` via `Nat.prime_def_minFac`.
- To prove `Nat.Prime n` from a divisor-based hypothesis, use `Nat.prime_def_minFac` + `Nat.minFac_prime` + `Nat.minFac_dvd` to reduce to "every prime divisor of `n` equals `n`" — cleaner than `Nat.prime_def_lt'` when the IH speaks about prime factors rather than arbitrary divisors.
