---
problem: Logic.toy_tree_mirror
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Logic.toy_tree_mirror — mirroring a labelled binary tree

## Statement

A labelled binary tree and its mirror, built from scratch:

- `toy_tree` — an **inductive type** of binary trees with natural-number
  labels at internal nodes: a `leaf : toy_tree` constructor and
  `node : ℕ → toy_tree → toy_tree → toy_tree`.
- `toy_mirror` — the mirror function (`toy_tree → toy_tree`): a leaf is
  its own mirror; `node v l r` mirrors to `node v` of the mirrored
  right child and the mirrored left child (children swapped, label kept).
- `toy_size` — the node count (`toy_tree → ℕ`): a leaf has size 0;
  `node v l r` has size `toy_size l + toy_size r + 1`.

### Deliverables

Forward-build the vocabulary above (snake_case names as given);
`MarkDeliverable` each claim; then `Ingest`:

- `toy_mirror_involutive` — mirroring twice is the identity:
  `∀ t, toy_mirror (toy_mirror t) = t`.
- `toy_mirror_size` — mirroring preserves the node count:
  `∀ t, toy_size (toy_mirror t) = toy_size t`.

### Proof shape

Both claims are structural induction on the tree: the leaf case is
definitional, the node case rewrites with the two induction hypotheses
(plus commutativity of addition for `toy_mirror_size`).

Do NOT introduce axioms or `sorry`-bearing shortcuts.
