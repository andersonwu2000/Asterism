import Mathlib.Data.Nat.Notation

namespace Library.Data.ToyListReverse

-- Forward rationale: The foundational data type for this problem's custom
-- vocabulary — an inductive type of natural-number lists built from scratch
-- (not a wrapper over Mathlib's `List`). Everything else (`toy_append`,
-- `toy_reverse`, `toy_length`, and the two deliverable claims) is built on top.
inductive toy_list : Type
  | nil : toy_list
  | cons : ℕ → toy_list → toy_list

-- Forward rationale: Element count on the custom `toy_list` type — the
-- length function underpinning the `toy_reverse_length` deliverable. Single
-- structural-recursion data def over the sibling `toy_list` inductive; does
-- not touch Mathlib's `List`. Independent of `toy_append`.
def toy_length : toy_list → ℕ
  | toy_list.nil => 0
  | toy_list.cons _ l => toy_length l + 1

-- Forward rationale: Concatenation on the custom `toy_list` type — the first
-- operation built on the foundational inductive. Structural recursion on the
-- first argument: appending to `nil` returns the other list; appending
-- `cons x l` is `cons x` of the recursive append. Needed by `toy_reverse`
-- and by the append helper lemmas (reverse-of-append, length-of-append)
-- the deliverables rely on.
def toy_append : toy_list → toy_list → toy_list
  | toy_list.nil, l => l
  | toy_list.cons x l, r => toy_list.cons x (toy_append l r)

-- Forward rationale: Naive reversal on the custom `toy_list` type, built on the
-- landed `toy_list` and `toy_append` bricks. Structural recursion: `nil`
-- reverses to itself; `cons x l` reverses to `toy_append (toy_reverse l)
-- (cons x nil)`. This is the last piece of the custom vocabulary and the
-- subject of both deliverables (`toy_reverse_involutive`, `toy_reverse_length`).
def toy_reverse : toy_list → toy_list
  | toy_list.nil => toy_list.nil
  | toy_list.cons x l => toy_append (toy_reverse l) (toy_list.cons x toy_list.nil)

-- Right-identity of `toy_append`: appending `nil` returns the list unchanged.
-- Plain structural induction on `l`; `nil` case is `rfl` (def unfolds), `cons`
-- case rewrites by the definitional step and the induction hypothesis.
theorem toy_append_nil : ∀ l : toy_list, toy_append l toy_list.nil = l  := by
  intro l
  induction l with
  | nil => rfl
  | cons x l ih => simp only [toy_append, ih]

-- toy_length distributes over toy_append: structural induction on `a`.
-- nil case unfolds toy_append/toy_length (0 + n); cons case rewrites via ih then omega.
theorem toy_length_append :
    ∀ a b : toy_list, toy_length (toy_append a b) = toy_length a + toy_length b  := by
  intro a b
  induction a with
  | nil => simp only [toy_append, toy_length, Nat.zero_add]
  | cons x l ih => simp only [toy_append, toy_length, ih]; omega

-- toy_append_assoc: associativity of toy_append by structural induction on the first list.
-- nil case is rfl; cons case unfolds toy_append twice and rewrites with the IH.
theorem toy_append_assoc : ∀ a b c : toy_list,
    toy_append (toy_append a b) c = toy_append a (toy_append b c)  := by
  intro a b c
  induction a with
  | nil => rfl
  | cons x l ih => simp only [toy_append, ih]

-- reverse-of-append distributes with order swapped; structural induction on `a`.
-- nil case closes via right-identity `toy_append_nil`; cons case rewrites by the
-- IH then re-associates via `toy_append_assoc`.
theorem toy_reverse_append : ∀ a b : toy_list,
    toy_reverse (toy_append a b) = toy_append (toy_reverse b) (toy_reverse a)  := by
  intro a b
  induction a with
  | nil => simp only [toy_append, toy_reverse, toy_append_nil]
  | cons x l ih => simp only [toy_append, toy_reverse, ih, toy_append_assoc]

-- Forward rationale: Manifest deliverable — reversal preserves the element
-- count. Structural induction on `l`: nil is definitional; cons rewrites
-- `toy_length (toy_append (toy_reverse l) (cons x nil))` via the landed
-- `toy_length_append` brick, applies the IH, and closes by ℕ arithmetic.
theorem toy_reverse_length : ∀ l : toy_list, toy_length (toy_reverse l) = toy_length l := by
  intro l
  induction l with
  | nil => rfl
  | cons x l ih =>
    change toy_length (toy_append (toy_reverse l) (toy_list.cons x toy_list.nil)) = toy_length l + 1
    rw [toy_length_append, ih]
    rfl

-- Forward rationale: The first Manifest deliverable — reversing twice is the
-- identity on the custom `toy_list`. Structural induction on `l`: the nil case
-- is definitional; the cons case unfolds one step of `toy_reverse`, rewrites by
-- the landed `toy_reverse_append` brick, collapses the singleton reverse
-- definitionally, and applies the IH. Needs decomposition + the append/reverse
-- helper bricks, hence Backward.
theorem toy_reverse_involutive : ∀ l : toy_list, toy_reverse (toy_reverse l) = l := by
  intro l
  induction l with
  | nil => rfl
  | cons x l ih =>
    change toy_reverse (toy_append (toy_reverse l) (toy_list.cons x toy_list.nil)) = _
    rw [toy_reverse_append, ih]
    rfl

end Library.Data.ToyListReverse
