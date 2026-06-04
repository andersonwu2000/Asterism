---
problem: Minif2f.mathd_numbertheory_155
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Minif2f.mathd_numbertheory_155 — imported from miniF2F

Original miniF2F theorem name: `mathd_numbertheory_155`.

## Statement
Finset.card (Finset.filter (fun x => x % 19 = 7) (Finset.Icc 100 999)) = 48

## Lemma hints

## Strategic notes
Imported via `python -m Tooling.adapters.minif2f`. No
per-problem hints — benchmark integrity (compare against
LeanDojo / DeepSeek-Prover head-to-head on the same
problem distribution).
