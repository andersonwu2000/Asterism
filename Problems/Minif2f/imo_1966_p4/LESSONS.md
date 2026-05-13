<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When deriving `x = (2m+1)·π/2^k` from `hm : 2^(k-1)·x = (2m+1)·π/2` (after `Real.cos_eq_zero_iff`) to contradict `h₀`, after `push_cast; rw [eq_div_iff hpow_ne, hpow]` use `linear_combination 2 * hm` (positive 2, not -2) — multiplying hm by 2 gives `2*2^(k-1)*x = (2m+1)*π`, matching the goal `x*(2*2^(k-1)) = (2m+1)*π` by ring.
- For telescoping sums whose summand uses Nat-subtracted indices (e.g. `2^(k-1)` with `k : ℕ`), `ring` won't close after the IH rewrite because `2^((m+1)-1)` and `2^m` are distinct atoms (Nat subtraction); use `simp` (which normalizes `(m+1)-1 = m` and the telescoping cancellation together) instead of, or before, `ring`.
- For `cot α − cot(2α) = 1/sin(2α)`-style identities, avoid `div_sub_div` (numerator-ordering side conditions cause fragile failures); instead `rw [Real.tan_eq_sin_div_cos, Real.tan_eq_sin_div_cos, Real.sin_two_mul, Real.cos_two_mul]` then close with `field_simp [hsin_α, hcos_α]; ring`.
- For telescoping sums over `Finset.Icc 1 n`, use induction with `cases n` (zero/succ) and `Finset.sum_Icc_succ_top (h : a ≤ b + 1)` to peel off the last element; the hypothesis arg matches the `b + 1` in `Finset.Icc a (b + 1)` directly, then `ring` closes after the IH rewrite.
- When deriving `x = ↑m * π / 2^k` from `hm : ↑m * π = 2^k * x` (after `Real.sin_eq_zero_iff`), avoid `field_simp + linarith` — linarith treats `x * 2^k` and `2^k * x` as distinct atoms; use `rw [eq_div_iff hpow_k_ne]` then `linarith [mul_comm ((2:ℝ)^k) x, hm.symm]` instead.
