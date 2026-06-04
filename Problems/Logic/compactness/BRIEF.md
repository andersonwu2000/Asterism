# compactness — BRIEF

_Auto-rendered from `Manifest.md` + `Library/`. The framework_
_inlines this file into `Context.md` for every Builder /_
_Backward dispatch on this problem._

## Sandbox
- Reads allowed without permission prompts:
  - This goal's problem dir (your cwd).
  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on Mathlib source.
- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant to this goal. Use Loogle / Grep on Mathlib instead.
- `Context.md` + `PAST_*.md` companion files: read-only.
- `patch.lean` is your single output. Lead with `--` annotation comments, then edit the body (Builder fills in the proof; Backward edits the strategy skeleton's body — signature locked). See the kind-specific prompt for layout.

## FORBIDDEN_LEMMAS (from Manifest.md)
**Do NOT use any of the following in your proof or in any sub-goal docstring; the integrator will reject the proposal.**
- FirstOrder.Language.Theory.compactness
- Theory.compactness
- Theory.IsSatisfiable.is_finitely_satisfiable

## Strategic notes (from Manifest.md)
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
