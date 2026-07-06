---
problem: Logic.toy_list_reverse
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Logic.toy_list_reverse — reversing a hand-rolled list

## Statement

A natural-number list type and its reversal, built from scratch (do NOT
reuse Mathlib's `List` — the point is the custom vocabulary):

- `toy_list` — an **inductive type** of lists of naturals: a
  `nil : toy_list` constructor and `cons : ℕ → toy_list → toy_list`.
- `toy_append` — concatenation (`toy_list → toy_list → toy_list`):
  appending to `nil` returns the other list; appending `cons x l` is
  `cons x` of appending `l`.
- `toy_reverse` — naive reversal (`toy_list → toy_list`): `nil` reverses
  to itself; `cons x l` reverses to `toy_append (toy_reverse l)
  (cons x nil)`.
- `toy_length` — the element count (`toy_list → ℕ`): `nil` has length 0;
  `cons x l` has length `toy_length l + 1`.

### Deliverables

Forward-build the vocabulary above (snake_case names as given);
`MarkDeliverable` each claim; then `Ingest`:

- `toy_reverse_involutive` — reversing twice is the identity:
  `∀ l, toy_reverse (toy_reverse l) = l`.
- `toy_reverse_length` — reversal preserves the element count:
  `∀ l, toy_length (toy_reverse l) = toy_length l`.

### Proof shape

Both claims are structural induction on the list. Expect to need small
helper lemmas about `toy_append` (e.g. reverse of an append, length of
an append) — prove them as their own bricks.

Do NOT introduce axioms or `sorry`-bearing shortcuts.
