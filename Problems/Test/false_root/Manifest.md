---
problem: Test.false_root
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Test.false_root

## Statement

The original universal claim (every prime stays prime after adding two)
is FALSE: kernel-proved counterexample n = 7 (7 is prime, 7 + 2 = 9 = 3 * 3
is composite) — see `not_main` / `prime_add_two_counterexample` in
proofs/L_not_main.lean. The checked examples (3→5, 5→7, 11→13) skip
exactly the primes 7, 13, 23, ... whose successor-by-two is composite.

Amended request: prove the true existential form in Root.lean —

`theorem main : ∃ n : ℕ, Nat.Prime n ∧ Nat.Prime (n + 2)`

(witness n = 3 or n = 5; closes by norm_num).
