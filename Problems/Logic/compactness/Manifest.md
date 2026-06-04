---
problem: Logic.compactness
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas:
  - FirstOrder.Language.Theory.compactness
  - Theory.compactness
  - Theory.IsSatisfiable.is_finitely_satisfiable
---

# compactness — propositional compactness from scratch

## Statement
∀ {α : Type} (S : Set (PropForm α)), (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S

## Lemma hints
- `Set.Finite`, `Set.Finite.toFinset`, `Set.subset_biUnion`
- `Classical.choice`, `Classical.byCases`
- `Mathlib.Order.Zorn` — `zorn_subset_nonempty` / `zorn_subset` for chain-bound argument
- `IsChain (· ⊆ ·)` (`Mathlib.Order.Chain`)
- `Set.mem_sUnion`, `Set.finite_singleton`, `Set.insert_subset_iff`
- `Classical.propDecidable` for case splits on whether a formula is in a set
- `PropForm.eval` is `Bool`-valued, decidable per atom assignment

## Strategic notes

The statement uses our own `PropForm` / `Valuation` / `Sat` from `Defs.lean`,
NOT Mathlib's `FirstOrder.Language` machinery — the Mathlib `Theory.compactness`
results are unreachable from this statement (and listed as forbidden anyway).

### Recommended root decomposition (already validated to prove in ~60 min)

Ship the root as **exactly** this 4-sub Backward, taking the lemma forms
verbatim — they have been verified independently provable end-to-end. Do
not rewrite into stronger / equivalent forms (e.g. subset-maximality
instead of pointwise, biconditional eval instead of one-directional);
those variants are equally valid mathematically but require materially
harder proofs and tend to drift Verify-time typeclass unification.

```lean
theorem main : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by
  intro α S hS
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ := main_sub_1 S hS
  have hneg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M :=
    main_sub_2 M hMfinsat hMmax
  have hconj : ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) :=
    main_sub_3 M hMfinsat hneg
  obtain ⟨v, hv⟩ := main_sub_4 M hneg hconj
  exact ⟨v, fun p hp => hv p (hSM hp)⟩
```

Sub-goal statements (use these signatures verbatim; the assembly above
expects exactly this typing):

```lean
theorem main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ p : PropForm α, p ∉ M →
        ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)

theorem main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M

theorem main_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)

theorem main_sub_4 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∃ v : Valuation α, ∀ p : PropForm α, p ∈ M → PropForm.eval v p = true
```

Mnemonic: sub_1 = Lindenbaum (pointwise-maximality form, NOT
subset-form), sub_2 = negation-completeness biconditional, sub_3 =
conj closure biconditional, sub_4 = canonical-model existence
(one-directional eval, NOT biconditional).

### Background

Expected 4-6 layer Backward decomposition. Fanout (sub-goals per
Backward) typically 3-5.
