<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `Nat.factorization_pos` does not exist in this Mathlib version; to prove `0 < y.factorization p` from `p ∈ y.primeFactors`, use `have : p ∈ y.factorization.support := by rwa [Nat.support_factorization]` then `Nat.pos_of_ne_zero (Finsupp.mem_support_iff.mp this)`.
- To prove `x.factorization = Finsupp.single p k` from `x.primeFactors = {p}` and a value hypothesis: apply `Finsupp.eq_single_iff` (reduces to `support ⊆ {p} ∧ f p = k`), then close the support branch with `Nat.support_factorization` (gives `x.factorization.support = x.primeFactors`) followed by the primeFactors hypothesis.
- Minif2f `patch.lean` namespace must use dots throughout (`Problems.Minif2f.mathd_numbertheory_221`), not an underscore-joined form — LSP `validate_file` silently accepts the wrong namespace but `lake build` fails with "constant not found".
- `Nat.factorization_prod_pow_eq_self` is deprecated — use `Nat.prod_factorization_pow_eq_self hx0` (argument order flipped in the name); its result is `x.factorization.prod (· ^ ·) = x`, not a `primeFactors`-indexed product, so reconstruct `x = p^k` by rewriting `x.factorization` to `Finsupp.single p k` then applying `Finsupp.prod_single_index (by simp)`.
- `Nat.card_divisors (h : n ≠ 0)` rewrites `n.divisors.card` into `∏ p ∈ n.primeFactors, (n.factorization p + 1)` — the algebraic entry point for divisor-count goals that need to reason about prime factorization structure rather than enumerate.
- For "prime p, p^N < K → p^N ∈ {list}" goals: bound p with `nlinarith [sq_nonneg p]`, then `interval_cases p <;> first | exact absurd hp (by decide) | decide` — the `first` branch closes non-prime cases via a false hypothesis, `decide` closes prime cases without `native_decide`.
- `Nat.divisors.card` goals on elements up to ~1000: use `fin_cases hx <;> decide` with `set_option maxRecDepth 2000` — the default depth (512) is insufficient and `native_decide` introduces a rogue axiom that fails the framework's axiom check.
