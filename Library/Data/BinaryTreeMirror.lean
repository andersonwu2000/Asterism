import Mathlib.Data.Nat.Notation

/-!
# Mirroring a labelled binary tree

This file defines a small inductive type of binary trees with natural-number
labels at internal nodes, together with the mirror (left-right swap) function
and the node-count function, and proves that mirroring is involutive and
preserves the node count.

## Main definitions

* `toy_tree`: binary trees with `ℕ` labels at internal nodes.
* `toy_size`: the number of internal nodes of a `toy_tree`.
* `toy_mirror`: the left-right mirror of a `toy_tree`.

## Main statements

* `toy_mirror_involutive`: mirroring a `toy_tree` twice is the identity.
* `toy_mirror_size`: mirroring a `toy_tree` preserves its node count.
-/

namespace Library.Data.BinaryTreeMirror

/-- Binary trees with `ℕ` labels at internal nodes: a tree is either a `leaf`
or a `node` carrying a label and a left and a right subtree. -/
inductive toy_tree : Type where
  | leaf : toy_tree
  | node : ℕ → toy_tree → toy_tree → toy_tree

/-- The number of internal nodes of a `toy_tree`: a `leaf` has size `0`, and
`node v l r` has size `toy_size l + toy_size r + 1`. -/
def toy_size : toy_tree → ℕ
  | toy_tree.leaf => 0
  | toy_tree.node _ l r => toy_size l + toy_size r + 1

/-- The left-right mirror of a `toy_tree`: a `leaf` is its own mirror, and
`node v l r` mirrors to `node v` of the mirrored right child and the mirrored
left child, i.e. the children are swapped and the label is kept. -/
def toy_mirror : toy_tree → toy_tree
  | toy_tree.leaf => toy_tree.leaf
  | toy_tree.node v l r => toy_tree.node v (toy_mirror r) (toy_mirror l)

/-- **Mirror invariance of size**: mirroring a `toy_tree` preserves its node
count. -/
theorem toy_mirror_size : ∀ t : toy_tree, toy_size (toy_mirror t) = toy_size t := by
  intro t
  induction t with
  | leaf => rfl
  | node v l r ihl ihr =>
    simp only [toy_mirror, toy_size, ihl, ihr, Nat.add_comm]

/-- **Involutivity of mirroring**: mirroring a `toy_tree` twice returns the
original tree. -/
theorem toy_mirror_involutive : ∀ t : toy_tree, toy_mirror (toy_mirror t) = t := by
  intro t
  induction t with
  | leaf => rfl
  | node v l r ihl ihr => simp only [toy_mirror, ihl, ihr]

end Library.Data.BinaryTreeMirror
