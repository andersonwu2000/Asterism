<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For concrete `padicValNat p N = k`, never use `native_decide` (introduces rogue axioms); instead factor `N = p^k * q^k` and chain `padicValNat.mul (by positivity) (by positivity)` + `padicValNat.pow k (by norm_num : p ≠ 0)` + `padicValNat.self (by norm_num)` + `padicValNat.eq_zero_of_not_dvd (by norm_num : ¬ p ∣ q^k)` — closes without a trailing tactic.
- Verified working API: `padicValNat p (p^n) = n` via `rw [padicValNat.pow n (by norm_num : p ≠ 0), padicValNat.self (by norm_num)]`; `padicValNat p (q^n) = 0` via `rw [padicValNat.eq_zero_of_not_dvd (by norm_num : ¬ p ∣ q^n)]` — `prime_pow` and `padicValNat_prime_prime_pow` (lesson 1) are unverified/nonexistent.
- After `rw [padicValNat.mul, padicValNat.pow y hp, padicValNat.self h1]`, `simp` reduces leftover `padicValNat p (q^x) = 0` to `¬ p ∣ q^x`; close with `fun h => absurd (Nat.Prime.dvd_of_dvd_pow (by norm_num : Nat.Prime p) h) (by norm_num)` — `padicValNat.prime_pow`/`padicValNat_prime_prime_pow` do NOT exist (confirmed).
- To pin a prime exponent from `2^x * 3^y = N`, apply `padicValNat p` to both sides: splits into `padicValNat p (2^x*3^y) = x_or_y` (uses `padicValNat.mul` + coprime-to-other-prime) and `padicValNat p N = const` (decide), then `rw [h₀]` + `omega`.
