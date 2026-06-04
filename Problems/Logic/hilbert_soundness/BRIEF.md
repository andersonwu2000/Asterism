# Logic.hilbert_soundness — BRIEF

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

## Strategic notes (from Manifest.md)
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
