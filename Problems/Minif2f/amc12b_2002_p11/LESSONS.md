<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For prime-triplet mod-3 residue sub-goals (e.g. `a % 3 = 1 → a ≤ 5`), `omega` derives `(a+k) % 3 = 0`; `Nat.dvd_of_mod_eq_zero` gives `3 ∣ (a+k)`; `h.eq_one_or_self_of_dvd 3 h3div` + `omega` pins `a+k = 3`; then `a` equals 1 or −1 (ℕ underflow), and `decide` closes the `Nat.Prime 0` or `Nat.Prime 1` contradiction.
- For lower-bound sub-goals on a prime triplet variable, `(h : Nat.Prime (a - k)).two_le` yields `a - k ≥ 2`; `omega` then derives `a ≥ k + 2` despite ℕ truncated subtraction, and any composite value in the gap (e.g. 4) is ruled out with `intro h; subst h; exact absurd h₀ (by decide)`, letting a final `omega` close `a ≥ k + 3`.
- For ℕ-prime parity sub-goals, `Nat.Prime.eq_two_or_odd` is the right case-split; in the `a=2` branch, ℕ subtraction underflow (`2 - b = 0` when `b ≥ 3`) turns `Nat.Prime (a - b)` into `Nat.Prime 0`, closed by `Nat.not_prime_zero`; in the odd branch, `Nat.Prime.eq_one_or_self_of_dvd` with `2 ∣ a+b` (via `omega`) closes the even-sum contradiction.
- Hypotheses force a=5, b=2: parity (Nat.Prime (a+b) with both odd ≥3 fails) pins b=2, then prime triplet {a-2,a,a+2}=={3,5,7} pins a=5; the goal expression reduces to Nat.Prime 17 which `decide` closes.
