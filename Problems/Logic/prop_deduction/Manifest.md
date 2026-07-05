---
problem: Logic.prop_deduction
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Logic.prop_deduction — deduction theorem for a Hilbert propositional calculus

## Statement

A self-contained classical propositional calculus, built from scratch
(mathlib has no syntactic propositional proof system):

- `prop_formula` — an **inductive type** of formulas: atoms over ℕ
  (`atom : ℕ → prop_formula`), implication
  (`imp : prop_formula → prop_formula → prop_formula`), and falsum
  (`bot : prop_formula`). Negation is the abbreviation `A.imp bot`.
- `prop_derives` — an **inductive** derivability relation
  `Set prop_formula → prop_formula → Prop` (write `Γ ⊢ A` informally)
  with exactly five rules:
  - `hyp` : `A ∈ Γ → Γ ⊢ A`
  - `axK` : `Γ ⊢ A.imp (B.imp A)`
  - `axS` : `Γ ⊢ (A.imp (B.imp C)).imp ((A.imp B).imp (A.imp C))`
  - `axDNE` : `Γ ⊢ ((A.imp bot).imp bot).imp A`
  - `mp` : `Γ ⊢ A.imp B → Γ ⊢ A → Γ ⊢ B`
- `prop_eval` — evaluation under a valuation
  (`(ℕ → Prop) → prop_formula → Prop`): an atom holds iff its
  valuation holds, `imp` is implication, `bot` is `False`.

### Deliverables

Forward-build the vocabulary above (snake_case names as given);
`MarkDeliverable` each claim; then `Ingest`:

- `prop_identity` — `Γ ⊢ A.imp A` for every `Γ A`.
- `prop_weakening` — `Γ ⊢ A → Γ ⊆ Δ → Δ ⊢ A`.
- `prop_deduction` — the deduction theorem:
  `prop_derives (insert A Γ) B → prop_derives Γ (A.imp B)`.
- `prop_soundness` — `prop_derives Γ A →` for every valuation `v`
  with `∀ B ∈ Γ, prop_eval v B`, also `prop_eval v A`.

### Proof shape

- `prop_identity`: the SKK derivation — `mp (mp axS axK) axK` with
  `B := A.imp A`.
- `prop_weakening`: induction on the derivation; only `hyp` touches `Γ`.
- `prop_deduction`: induction on the derivation of `insert A Γ ⊢ B`:
  the `hyp` case splits `B = A` (use `prop_identity`) vs `B ∈ Γ`
  (axK + mp); each axiom case is axK + mp; the `mp` case combines the
  two induction hypotheses via axS.
- `prop_soundness`: induction on the derivation; axiom cases are
  propositional tautologies (`tauto` after unfolding `prop_eval`).

This calculus is the stepping stone toward propositional completeness
(Lindenbaum / maximal consistent sets) and, further, Gödel completeness.
Do NOT introduce axioms or `sorry`-bearing shortcuts.
