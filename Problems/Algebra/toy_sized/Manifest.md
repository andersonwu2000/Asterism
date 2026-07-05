---
problem: Algebra.toy_sized
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Algebra.toy_sized — a class, a structure, and a named instance

## Statement

Minimal typeclass-resolution vocabulary, built from scratch:

- `toy_sized` — a **class** over a type `α` with a single field
  `tsize : α → ℕ`.
- `toy_pair` — a **structure** with two fields `a b : ℕ`.
- `toy_pair_sized` — a **named instance** `toy_sized toy_pair` whose
  `tsize` is `a + b`. (Name it exactly `toy_pair_sized` — the
  framework requires named instances.)

### Deliverables

Forward-build the vocabulary above; `MarkDeliverable` the claim; then
`Ingest`:

- `toy_pair_tsize_val` — `toy_sized.tsize (toy_pair.mk 2 3) = 5`,
  where `tsize` is found by typeclass resolution (do not name the
  instance in the statement).

### Proof shape

Unfold `tsize` for the registered instance; `rfl` or `simp` closes it.

Do NOT introduce axioms or `sorry`-bearing shortcuts.
