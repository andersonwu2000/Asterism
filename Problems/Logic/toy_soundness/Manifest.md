---
problem: Logic.toy_soundness
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Logic.toy_soundness — soundness of a two-rule toy Hilbert system

## Statement

A toy propositional language and its semantics, built from scratch:

- `toy_formula` — an **inductive type** of formulas over natural-number
  atoms: an atom constructor `atom : ℕ → toy_formula` and implication
  `imp : toy_formula → toy_formula → toy_formula`.
- `toy_model` — a **structure** bundling a valuation `val : ℕ → Prop`.
- `toy_eval` — evaluation of a formula in a model (`toy_model →
  toy_formula → Prop`): an atom holds iff its valuation holds,
  `imp A B` holds iff `A`'s evaluation implies `B`'s.
- `toy_derives` — an **inductive** derivability predicate
  (`toy_formula → Prop`) with exactly two rules: axiom scheme K,
  `⊢ A.imp (B.imp A)` for all `A B`, and modus ponens (from `⊢ A.imp B`
  and `⊢ A` conclude `⊢ B`).
- `has_toy_depth` — a **class** over a type `α` exposing a single
  field `depth : α → ℕ` (an abstract size interface; no instance is
  required by the claims below).

### Deliverables

Forward-build the vocabulary above (snake_case names as given);
`MarkDeliverable` each claim; then `Ingest`:

- `toy_soundness` — every derivable formula is true in every model:
  `toy_derives A → ∀ M, toy_eval M A`.
- `toy_depth_pos` — for any `α` with `[has_toy_depth α]` and any
  `x : α`, `0 < has_toy_depth.depth x + 1`.

### Proof shape

`toy_soundness` is induction over the `toy_derives` derivation: the K
case is propositional logic (`intro`/`exact`), the modus-ponens case
applies the two induction hypotheses. `toy_depth_pos` is arithmetic
(`Nat.succ_pos`).

Do NOT introduce axioms or `sorry`-bearing shortcuts.
