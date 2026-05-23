---
problem: LinearAlgebra.qr_decomposition
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.qr_decomposition — QR decomposition of an invertible matrix

## Statement
∀ {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ),
  A.det ≠ 0 →
  ∃ (Q R : Matrix (Fin n) (Fin n) ℝ),
    Q * Matrix.transpose Q = 1 ∧
    R.BlockTriangular id ∧
    A = Q * R

## Setting
- Real `n × n` invertible matrix `A`.
- Conclusion: factor `A = Q * R` where
  - `Q` is orthogonal (`Q * Qᵀ = 1`, equivalent to columns being orthonormal),
  - `R` is upper triangular (encoded as `BlockTriangular id`).

The invertibility hypothesis (`det ≠ 0`) makes the QR factorization unique up to sign and
keeps `R` with non-singular diagonal. The rectangular / rank-deficient generalizations
(`thin QR` / `full QR` of an `m × n` matrix) are natural follow-ups; this problem covers
the canonical square invertible case to keep scope tight.

## Lemma hints

Likely relevant mathlib modules:

- `Mathlib/Analysis/InnerProductSpace/GramSchmidtOrtho.lean` — `gramSchmidt`,
  `gramSchmidtNormed`, `gramSchmidtBasis`, `gramSchmidt_triangular`,
  `span_gramSchmidt`.
- `Mathlib/Analysis/InnerProductSpace/PiL2.lean` — `EuclideanSpace`,
  `EuclideanSpace.basisFun`, standard inner product on `ℝⁿ`.
- `Mathlib/LinearAlgebra/Matrix/Block.lean` — `BlockTriangular`.
- `Mathlib/LinearAlgebra/Matrix/Orthogonal.lean` (if present) — orthogonal matrix
  predicates; otherwise express `Q.IsOrthogonal` directly via `Q * Qᵀ = 1`.

## Strategic notes

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
