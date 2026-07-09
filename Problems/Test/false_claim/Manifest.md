---
problem: Test.false_claim
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Test.false_claim

## Statement

The original conjecture — every prime `n : ℕ` stays prime after adding
two — is FALSE: `n = 7` is prime but `7 + 2 = 9 = 3 * 3` is not. The
computed examples (3→5, 5→7, 11→13) were twin-prime coincidences. The
deliverable is the kernel-checked disproof:
`¬ ∀ n : ℕ, Nat.Prime n → Nat.Prime (n + 2)`.

### Deliverables

`MarkDeliverable` the disproof; then `Ingest`:

- `not_forall_prime_plus_two_prime`

Do NOT introduce axioms or `sorry`-bearing shortcuts.
