<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To close ring-arithmetic goals in `ZMod p` (e.g. `a = -1` from `heq : a + 1 = 0`), use `linear_combination heq`; `linarith` fails because `ZMod p` is unordered.
- For Fermat's little theorem in `ZMod p`, use `ZMod.pow_card_sub_one_eq_one (h : x ≠ 0)` with `haveI : Fact p.Prime := ⟨hp⟩` in scope — it takes only the non-zero witness as explicit arg; passing the prime first gives a type mismatch.
- To prove `(a : ZMod p)^k = 1` from several `a^kᵢ = 1` facts: lift each via `orderOf_dvd_of_pow_eq_one` to `orderOf a ∣ kᵢ`, combine with `Nat.dvd_gcd`, then `.trans` a separate `Nat.gcd kᵢ… ∣ k` fact and close with `orderOf_dvd_iff_pow_eq_one.mp` — cleaner than `pow_eq_one_iff_modEq` chains.
- When `heq : f e = n` for a numeral `n` that also appears inside `e` (e.g. `Nat.minFac (m/3) = 3` with `3` inside `m/3`), term-mode `heq ▸ h` rewrites ALL occurrences of `n` and corrupts the other subterm; use `have := h; rw [heq] at this; exact this` to safely rewrite only `f e`.
- To convert `(k : ZMod m) = 0` to `m ∣ k`, use `CharP.cast_eq_zero_iff (ZMod m) m k` — `ZMod.natCast_zmod_eq_zero_iff_dvd` does not exist in this Mathlib build; `CharP.cast_eq_zero_iff` works because `ZMod m` carries `CharP (ZMod m) m`.
- To lift `a ∣ b` to a pointwise factorization inequality, use `Nat.factorization_le_iff_dvd (ha : a ≠ 0) (hb : b ≠ 0) : a.factorization ≤ b.factorization ↔ a ∣ b`; then evaluate at a prime and rewrite `(n^k).factorization p` via `Nat.factorization_pow` + `Finsupp.smul_apply` + `smul_eq_mul` to get `k * n.factorization p`, with `linarith` closing.
- For 3-adic valuation arguments on this problem, use `Nat.factorization n 3` (cleaner than `padicValNat`/`multiplicity`); bridge to divisibility via `Nat.Prime.pow_dvd_iff_le_factorization hp h_ne_zero : p^k ∣ n ↔ k ≤ n.factorization p`, then `omega` closes mixed valuation/divisibility goals.
- To reduce `(a : ZMod n)^m` to `(a : ZMod n)^(m % k)` given `hper : a^k = 1`: write `conv_lhs => rw [← Nat.div_add_mod m k]` then `rw [pow_add, pow_mul, hper, one_pow, one_mul]`; afterwards close all residue cases with `interval_cases (m % k) <;> simp_all (config := { decide := true })`.
- To push a ℕ-cast through `+`/`^` in a `ZMod p` equality (e.g., `h : ↑(2^n+1) = 0` → goal `(2:ZMod p)^n + 1 = 0`), use `simpa using h` — `push_cast at h` silently fails to simplify in this compound-expression form, while `simpa` succeeds by normalizing both sides.
- For ℕ divisibility goals with truncated subtraction (e.g. `3 ∣ a^2 - a + 1`), use `zify [hle]` where `hle : a ≤ a^2` is proved by `nlinarith` from a lower bound on `a`; then supply an explicit dvd witness and close with `nlinarith [sq_nonneg k]` — `linarith` alone fails on the nonlinear residual.
