---
problem: Topology.brouwer_fixed_point
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas:
  - sperner*
  - Sperner*
  - kuhn*
  - Kuhn*
  - simplicial_label*
  - barycentric_label*
  - rainbow_label*
---

# Topology.brouwer_fixed_point — Brouwer fixed-point theorem (convex compact set in finite-dim inner product space)

## Statement
∀ {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
  [FiniteDimensional ℝ E] {K : Set E}
  (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K)
  {f : E → E} (hcont : ContinuousOn f K) (hmaps : Set.MapsTo f K K),
  ∃ x ∈ K, f x = x

## Setting
- `E` finite-dim inner product space over ℝ
- `K ⊆ E` nonempty, compact, convex
- `f : E → E` continuous on `K`, maps `K` to `K`

## Lemma hints
- `Set.MapsTo` / `Set.Nonempty`
- `IsCompact` / `Convex`
- `ContinuousOn` / `Continuous` / `Continuous.comp`
- `Metric.closedBall` / `EuclideanSpace` / `Metric.sphere`
- `FiniteDimensional` / `Module.finrank`
- `Homeomorph`
- `IsCompact.exists_isMinOn` / `IsCompact.exists_forall_le`

## Strategic notes

### Spine (mandatory)

```
Brouwer  ⇐  No-retraction(Dⁿ → Sⁿ⁻¹)  ⇐  H_{n-1}(Sⁿ⁻¹) ≠ 0  ∧  H_{n-1}(Dⁿ) = 0
```

Only allowed algebraic invariant: **singular homology**.

1. Reduce `K` to `closedBall 0 1` (or a standard simplex) via `Homeomorph`,
   transport the fixed-point problem.
2. No-retraction lemma: `¬ ∃ r : Dⁿ → Sⁿ⁻¹` continuous with `r ∘ i = id`
   (where `i : Sⁿ⁻¹ ↪ Dⁿ`). Brouwer follows by the standard
   contrapositive (assume no fixed point → build retraction via the ray
   `f(x) → x` extended to `Sⁿ⁻¹` → contradiction).
3. No-retraction via `H_{n-1}` functor: `r ∘ i = id` would give a
   factorization `ℤ ≅ H_{n-1}(Sⁿ⁻¹) → H_{n-1}(Dⁿ) = 0 → ℤ` equal to `id`.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type /
   functor / theorem name you intend to build, plus synonym variants.
   Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape
   second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge
   lemma** to this problem's types/naming. Do not reconstruct any
   foundational layer (chain complex, homology functor, homeomorph
   constructors, etc.).
4. Only after confirmed missing, inject a new Forward. The
   `## Forward rationale` first line must state `Grep + Loogle
   confirmed missing` and list the exact keywords searched.

Strategist: when a Forward output is an obvious mathlib candidate that
the agent did not Grep, `ConfirmShelve` it and re-inject a Forward
requiring the search step first.

### Forbidden angles

- Sperner / Kuhn / any simplicial labelling counting argument
  (`forbidden_lemmas` covers the namespace).
- Homotopy-group route (πₙ₋₁(Sⁿ⁻¹)) — violates the spine.
- Brouwer degree theory — derives from homology, circular.
- Winding-number tooling from `residue_thm` — bypasses the spine.
- IVT for n=1 then claiming the general case — logically invalid.
