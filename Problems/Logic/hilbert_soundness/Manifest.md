---
problem: Logic.hilbert_soundness
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Logic.hilbert_soundness — Soundness of a Hilbert proof system for first-order sentences

## Statement
∀ {L : FirstOrder.Language} {T : L.Theory} {φ : L.Sentence},
  Problems.Logic.hilbert_soundness.Derivable T φ → T ⊨ᵇ φ

## Setting
- `L` an arbitrary first-order language; `T : L.Theory` a set of `L`-sentences.
- `Derivable T φ` (defined in `Defs.lean`) is a Hilbert-style proof relation —
  the classical implicational fragment over first-order sentences: hypotheses,
  modus ponens, the `K`/`S` combinator axioms, double-negation elimination.
- `⊨ᵇ` is mathlib's semantic consequence (`Theory.ModelsBoundedFormula`): `φ`
  holds in every model of `T`.
- Conclusion: derivability implies semantic consequence — **soundness**.

This is the easy half of, and a stepping stone toward, Gödel's completeness
theorem (`T ⊨ φ ↔ T ⊢ φ`). mathlib has the semantic side and Compactness but no
syntactic `⊢` at all, so even stating completeness requires first supplying a
proof calculus; this problem supplies a propositional-fragment calculus and
proves its soundness. (First-order quantifier rules — generalization via
`realize_all`, instantiation via `realize_subst` — are a natural extension.)

## Lemma hints

Likely relevant mathlib:

- `Mathlib/ModelTheory/Semantics.lean` — `BoundedFormula.Realize`,
  `realize_imp`, `realize_bot`, `realize_not`.
- `Mathlib/ModelTheory/Satisfiability.lean` — `Theory.ModelsBoundedFormula`
  (`⊨ᵇ`), `Theory.Model`, `realize_sentence_iff`.

## Strategic notes

The proof is structural induction on `Derivable`:

1. `hyp`: `φ ∈ T` and any model of `T` realizes every sentence of `T`.
2. `mp`: `realize_imp` — validity is closed under modus ponens.
3. `ax_k` / `ax_s`: classical propositional tautologies; after unfolding
   `Realize` of the implications, close by `tauto`.
4. `ax_dne`: double-negation elimination — classical, `tauto` (or `by_contra`).

Each axiom is a sentence whose realization unfolds (via the `realize_*` simp
lemmas) to a propositional tautology over `Prop`. No quantifier reasoning is
needed for this fragment.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def`: `Grep` mathlib
(`.lake/packages/mathlib/Mathlib/ModelTheory/**`) for the realize lemma you
need (`realize_imp`, `realize_bot`, `realize_sentence_iff`, the `Theory.Model`
membership lemma) and reuse it. Do not reconstruct the semantic layer.

### Forbidden angles

- Do not redefine `⊨` or the semantics — reuse mathlib's `ModelTheory`.
- Each problem stands alone; no cross-problem citation.
