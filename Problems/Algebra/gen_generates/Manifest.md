---
problem: Algebra.gen_generates
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# gen_generates — exam IV cyclic group generator lemma

## Statement
∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n), x ∈ Subgroup.zpowers (gen n)

## Lemma hints
- `Subgroup.mem_zpowers_iff` — `x ∈ Subgroup.zpowers g ↔ ∃ k : ℤ, g^k = x`
- `Multiplicative.ofAdd`, `Multiplicative.toAdd`, `Multiplicative.toAdd_zpow`
- `AddSubgroup.mem_zmultiples_iff` — additive analogue
- `ZMod.intCast_cast`, `ZMod.intCast_zmod_cast`
- `Int.cast` / `zsmul` lemmas for ZMod
- The additive form: every `x : ZMod n` equals `(x.val : ℤ) • 1` (i.e. `x.val * 1 = x`)

## Strategic notes
`G n = Multiplicative (ZMod n)`, `gen n = Multiplicative.ofAdd (1 : ZMod n)`.

Goal: for any `x : G n`, exhibit `k : ℤ` such that `(gen n) ^ k = x`.

Translation through `Multiplicative`:
`(Multiplicative.ofAdd a) ^ k = Multiplicative.ofAdd (k • a)` (zsmul on the
additive side). So `(gen n)^k = x` ⟺ `k • (1 : ZMod n) = Multiplicative.toAdd x`.

In `ZMod n`, `k • (1 : ZMod n) = (k : ZMod n)` (integer cast). And every
element of `ZMod n` is the image of some integer cast (e.g. `Multiplicative.toAdd x`
itself reinterpreted as ℤ via `.val`). So a valid `k` is `((Multiplicative.toAdd x).val : ℤ)`.

Alternate route: Mathlib's `IsCyclic` instance for `ZMod n` might be available;
the multiplicative wrapping inherits it. If you can find `IsCyclic.exists_pow_eq`
or similar, the proof is one application.
