# LinearAlgebra.qr_decomposition — BRIEF

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
Standard textbook proof skeleton (agents may follow or deviate):

1. View columns of `A` as `n` vectors in `EuclideanSpace ℝ (Fin n)`. Invertibility ↔
   linear independence.
2. Apply Gram-Schmidt to those columns: get an orthonormal basis `q₁, …, qₙ` with the
   triangular property `qⱼ ∈ span{a₁, …, aⱼ}` (mathlib's
   `gramSchmidt_triangular` / `span_gramSchmidt_Iic`).
3. Define `Q` with columns `qⱼ`; orthonormality of the columns gives `Qᵀ Q = 1` ⇔
   `Q Qᵀ = 1` (square case).
4. Define `R := Qᵀ * A`. The triangular property of the Gram-Schmidt process gives
   `R` upper-triangular.
5. `Q * R = Q * Qᵀ * A = A`.

Proof angle is the agents' choice; alternative routes (Householder reflections, Givens
rotations) are valid but mathlib coverage of those is thin — the Gram-Schmidt route
above is the cleanest reuse path.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (Gram-Schmidt, matrix
   conversions, orthonormal basis machinery, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords
   searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did not
`Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Citing the entire result as a single mathlib theorem if you find one (surface via
  `RequestUserAmend`).
