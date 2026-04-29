---
problem: compactness
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

## Difficulty
5

## Mathlib hints
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
The proof must structure: (a) Lindenbaum extension of S to a maximal
finitely-satisfiable superset using Zorn, (b) the canonical valuation read off
the maximal set is a model of S, (c) maximal-finsat sets behave well under
`conj` and `neg` so the truth lemma follows by structural induction on
`PropForm`.

Expected 4-6 layer Backward decomposition. Fanout (sub-goals per Backward) typically 3-5.
