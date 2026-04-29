---
problem: wilson
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas:
  - ZMod.wilsons_lemma
  - Nat.Prime.wilsons_lemma
---

# wilson — Freek 100 #51 reformulated on Nat

## Statement
∀ p : ℕ, p.Prime → Nat.factorial (p - 1) % p = p - 1

## Difficulty
4

## Mathlib hints
- ZMod.val_natCast (Data/ZMod/Basic.lean:89)
- ZMod.val_neg_one (Data/ZMod/Basic.lean:540)
- Nat.mod_eq_of_lt
- Nat.Prime.two_le

## Strategic notes
此題 reformulated 過、ZMod 形式直接用會被擋（forbidden_lemmas 含 ZMod.wilsons_lemma）；要走 Mathlib bridge：用 ZMod.val_natCast 把 Nat % 跟 ZMod.val 接起來。
