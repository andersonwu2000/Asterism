<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To cancel coprime prime-power factors from `p^k ∣ A * B` over ℤ: `Prime.coprime_iff_not_dvd` converts `¬p ∣ x` to `IsCoprime p x`; `IsCoprime.pow_left` lifts to `IsCoprime (p^k) x`; chain with `IsCoprime.mul_right` for products; then `IsCoprime.dvd_of_dvd_mul_left` cancels A to yield `p^k ∣ B`; use `mul_dvd_mul_iff_left` to cancel an explicit scalar factor beforehand.
- To prove `p^k ∣ q` from `p^(2k) ∣ q^2` (prime `p`), iterate `Prime.dvd_of_dvd_pow` + `obtain`/`subst`; after each subst, `ring_nf at this ⊢; omega` reduces `p^(2k) ∣ (p*r)^2` to `p^(2k-2) ∣ r^2` without any intermediate lemma.
- For `n ∣ x` with `0 < x` over ℤ, `Int.le_of_dvd` gives `n ≤ x`; combined with `nlinarith [sq_nonneg (a+b)]` it refutes small-sum cases for `7^3 ∣ a^2+a*b+b^2` without case-enumeration.
