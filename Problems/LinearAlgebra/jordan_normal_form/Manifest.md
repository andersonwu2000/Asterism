---
problem: LinearAlgebra.jordan_normal_form
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.jordan_normal_form — Jordan normal form (algebraic form)

## Statement
∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    Problems.LinearAlgebra.jordan_normal_form.IsJordanForm
      (LinearMap.toMatrix b b T)

## Setting
- `K` algebraically closed field (e.g. `ℂ`).
- `V` finite-dim `K`-vector space.
- `T` arbitrary `K`-linear endomorphism of `V`.
- Conclusion: there is a basis `b` of `V` such that `T`'s matrix in that basis is in
  Jordan normal form — diagonal carries the eigenvalues (with algebraic multiplicity),
  super-diagonal has `0`s and `1`s with `1` only between matching adjacent diagonal entries
  (i.e. inside a single Jordan block), all other entries zero.

`IsJordanForm` is defined in `Defs.lean` as the structural predicate above. Block ordering
is not constrained (matches the "up to permutation" convention in standard textbooks).

## Lemma hints

Likely relevant mathlib modules:

- `Mathlib/LinearAlgebra/Eigenspace/` — `Module.End.exists_eigenvalue`,
  `Module.End.maxGenEigenspace`, `Module.End.iSup_maxGenEigenspace_eq_top`
  (generalized eigenspaces span `V` over algClosed `K`),
  `Module.End.genEigenspace_restrict_eq_top`.
- `Mathlib/LinearAlgebra/Eigenspace/Semisimple.lean` — semisimple operator structure
  (commuting-with-T decomposition lemmas).
- `Mathlib/LinearAlgebra/Matrix/Block.lean`,
  `Mathlib/LinearAlgebra/Matrix/ToLin.lean` — `BlockTriangular`, `LinearMap.toMatrix`.
- `Mathlib/Algebra/DirectSum/LinearMap.lean`,
  `Mathlib/LinearAlgebra/DirectSum/Module.lean` — direct-sum machinery for the
  primary-decomposition step.
- `Mathlib/LinearAlgebra/Nilpotent.lean` — nilpotent operator basics
  (`IsNilpotent`, nilpotency-index lemmas).

## Strategic notes

The proof method is the agents' choice. The standard textbook chain:

1. **Primary decomposition**: over algClosed `K`, `V` decomposes as a direct sum of
   generalized eigenspaces `V = ⊕ ker((T - λ I)^n_λ)`. Mathlib gives the underlying
   `iSup` form; package it as an internal direct-sum decomposition for downstream use.
2. **Reduction to nilpotent**: on each generalized eigenspace `V_λ`, the operator
   `N := (T - λ I)` restricted to `V_λ` is nilpotent.
3. **Jordan basis for a nilpotent operator**: from the kernel filtration
   `ker N ⊆ ker N² ⊆ ... ⊆ ker N^d = V_λ`, build a Jordan basis (chains of vectors
   `v, N v, N² v, ...` ending at `0`). The matrix of `N` in this basis is the
   strictly-upper-triangular part of a Jordan-block diagonal.
4. **Assemble**: combine bases from each generalized eigenspace, shift by `λ I` on each
   block to recover `T`'s matrix as a Jordan form.

Other routes (Smith normal form on `K[x]`-module, semisimple+nilpotent split via
Chevalley–Jordan, abstract algebra angles) are valid too — the spine above is just the
most concrete classical path.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (eigenspace machinery,
   nilpotent operator infrastructure, direct-sum decomposition, matrix↔basis conversion,
   etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords
   searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did not
`Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Citing Smith normal form for `K[x]`-modules from mathlib if it would let you sidestep
  building the structural understanding (it would technically work but loses the stress
  signal — the point of this problem is to exercise the framework on a deep multi-stage
  decomposition, not to thread an algebraic shortcut). Avoid `Module.basisOfPid` /
  `Submodule.basisOfPid` family for this purpose.
- Citing a sibling problem (e.g. `Problems/LinearAlgebra/schur_triangularization`) —
  sandbox blocks cross-problem reads; each problem stands alone.
- Citing the entire result as a single mathlib theorem if one exists (surface via
  `RequestUserAmend`).
