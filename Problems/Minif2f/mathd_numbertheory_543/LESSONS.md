<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- After `Nat.Coprime.card_divisors_mul` splits a product, close each `(Nat.divisors (p^n)).card = n+1` with `rw [Nat.divisors_prime_pow (by norm_num : Nat.Prime p)]; simp` — `decide` fails even for small primes/exponents.
- To bridge `∑ k ∈ s, 1` ↔ `s.card` for divisor-count goals, use `rw [← Finset.card_eq_sum_ones]` directly — `simp [Finset.card_eq_sum_ones]` loops against `Finset.sum_const`.
- `native_decide` is framework-banned (rogue axiom rejected at lake build); for `Nat.divisors (large_n)` goals plain `decide` hits maxRecDepth/maxHeartbeats — decompose via `Nat.Coprime.card_divisors_mul` + prime-power factorization instead.
