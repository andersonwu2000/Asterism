<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For the pair invariant inductive step (`t(m+P)%k = t m%k ∧ t(m+P+1)%k = t(m+1)%k`), first conjunct on `succ k'` closes via `ih.2` after a `k'+1+P = k'+(P+1)` `ring`-rewrite; second conjunct: derive `t(k'+P+2) = t(k'+P) + t(k'+P+1)` from `hrec (k'+P+2)` using omega-based subtraction rewrites (`e1 : k'+P+2 - 2 = k'+P`; `rw [e1,e2] at h`), then close mod k via `rw [hr_step, hr_2, Nat.add_mod, ih.1, ih.2, ← Nat.add_mod]`.
- For Pisano-periodicity goals `∀ n, t (n+P) % m = t n % m` (with t Fibonacci-like via `hrec : ∀ n > 1, t n = t (n-2) + t (n-1)`), induction-strengthen to a pair invariant `∀ n, t (n+P) % m = t n % m ∧ t (n+P+1) % m = t (n+1) % m`; strengthened form admits direct (not strong) `Nat.rec` induction since `hrec` at `n+P+2` lifts the pair forward, and combinator is one-liner `(pair n).1`.
- For concrete base-case goals `t n % 7 = r`, unroll via `have h_k : t k = t (k-2) + t (k-1) := by have := hrec k (by norm_num); simp at this; exact this` for k=2..n then close with `omega`; `simp` reduces the concrete Nat subtractions (e.g. `15 - 2 = 13`) inside the `hrec` hypothesis.
- Alternative for `∀ k, t (16*k + r) % 7 = r'`: decompose into abstract `∀ a, a ≡ r [MOD 16] → t a % 7 = t r % 7` (mirrors `t_eq_t_5_mod_7` shape) plus base `t r % 7 = r'`; combinator is one-line `(h_per (16*k+r) hmod).trans h_base` after `hmod := by unfold Nat.ModEq; omega` — avoids `induction k`.
- For `∀ k, t (16*k + r) % 7 = r'` decompose into a generic Pisano period lemma `∀ n, t (n+16) % 7 = t n % 7` plus base `t r % 7 = r'`; combinator is `induction k` with step rewrite `16*(k+1)+r = (16*k+r)+16` (by `ring`), then `rw [heq, hperiod]; exact ih`.
- For Pisano-residue sub-goals (t a/b/c % 7 = r given x ≡ r [MOD 16]), decompose to one lemma `∀ k, t (16*k + r) % 7 = r'` and combinator: `unfold Nat.ModEq at h; omega` to get `c % 16 = r`, then `Nat.div_add_mod c 16` + `omega` to rewrite `c = 16*(c/16) + r`, then apply.
