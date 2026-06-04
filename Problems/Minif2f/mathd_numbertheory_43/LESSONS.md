<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove `(Nat.factorial n).factorization p = K` for concrete values, rewrite with `Nat.factorization_factorial hp (by norm_num : Nat.log p n < b)` (reducing to `∑ i ∈ Finset.Ico 1 b, n / p ^ i = K`), then close with `decide` — `norm_num` cannot evaluate the Ico sum.
- For the upper-bound direction `c^n ∣ N → n ≤ K` with composite `c` (e.g. `15^n ∣ 942! → n ≤ 233`), no coprime split is needed — reduce to a single tight-valuation prime `p ∣ c` via `dvd_trans (pow_dvd_pow_of_dvd (h : p ∣ c) n) hcN : p^n ∣ N`; the coprime/`Nat.mul_pow` machinery is only required for the membership direction (`c^K ∣ N`).
- For `p^k ∣ Nat.factorial n` (e.g. `3^233 ∣ 942!`, `5^233 ∣ 942!`), the lemma is `Nat.Prime.pow_dvd_iff_le_factorization hp (Nat.factorial_ne_zero n) |>.mpr` — reduces to `k ≤ (Nat.factorial n).factorization p`; note `Nat.Prime.pow_dvd_factorial` / `Nat.Prime.multiplicity_factorial` do NOT exist as dot-notation (they project through `Irreducible` and fail).
- For 15^n ∣ 942! split as `(15:ℕ)^n = 3^n * 5^n` via `Nat.mul_pow` then close with `Nat.Coprime.mul_dvd_of_dvd_of_dvd` on `(by decide : Nat.Coprime 3 5).pow_left _ |>.pow_right _`; v₅(942!) = 188+37+7+1 = 233 is tight (v₃(942!) = 467 is slack), so the IsGreatest upper bound reduces entirely to the 5-adic side.
- The `942!` factorial postfix in this problem's signature is `Nat.factorial` scoped notation — patch.lean / sub-goal stubs need `open Nat` (or rewrite as `Nat.factorial 942`) since `Defs.lean`'s `open Nat` is file-scoped and does not propagate via import.
