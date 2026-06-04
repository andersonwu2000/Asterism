---
problem: Geometry.banach_tarski
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.banach_tarski — Banach–Tarski paradox on the closed unit ball in ℝ³

## Statement
∃ (f g : Equidecomp E (E ≃ᵢ E)),
  Disjoint f.source g.source ∧
  f.source ∪ g.source = Metric.closedBall (0 : E) 1 ∧
  f.target = Metric.closedBall (0 : E) 1 ∧
  g.target = Metric.closedBall (0 : E) 1

## Setting
`E := EuclideanSpace ℝ (Fin 3)`; `Equidecomp X G` is the mathlib type from
`Mathlib/Algebra/Group/Action/Equidecomp.lean`. The acting group is
`E ≃ᵢ E` (self-isometries of `E`); `Group (α ≃ᵢ α)` is mathlib-provided
and `MulAction (E ≃ᵢ E) E` is set up in `Defs.lean`. Reading: the closed
unit ball `B₀ := Metric.closedBall 0 1` splits into two disjoint pieces
`f.source ⊔ g.source = B₀`, and each piece is equidecomposable to the
whole `B₀` — the "doubling" form of Banach–Tarski.

- Ambient space `E = EuclideanSpace ℝ (Fin 3)`. Closed unit ball
  `B₀ = Metric.closedBall (0 : E) 1`.
- Acting group: `E ≃ᵢ E`, the self-isometries of `E` (includes rotations,
  reflections, translations). mathlib gives `Group (α ≃ᵢ α)` (composition /
  refl / symm). The induced action `g • x = g x` is set up locally in
  `Defs.lean` via `MulAction (E ≃ᵢ E) E`.
- `Equidecomp X G` is a `PartialEquiv X X` bundled with a `Finset G`
  witness that each `f a` is `γ • a` for some `γ` in the witness. Same as
  "equivalence under finitely-many rigid motions applied to disjoint pieces."

Choosing `E ≃ᵢ E` (full isometry group) over a strict subgroup like
`Matrix.specialOrthogonalGroup (Fin 3) ℝ` is intentional — the textbook
theorem is naturally stated for the full Euclidean group, and the proof
needs both rotations and translations.

## Lemma hints

Likely relevant mathlib modules:

- `Mathlib/Algebra/Group/Action/Equidecomp.lean` — `Equidecomp` structure,
  `refl` / `trans` / `symm` / `restr` / `IsDecompOn`. Note the file lists
  several Schroeder-Bernstein-style theorems as `TODO`; those are missing
  and may need to be built here.
- `Mathlib/GroupTheory/FreeGroup/Basic.lean` (+ `Reduce`, `IsFreeGroup`,
  `NielsenSchreier`, `Orbit`, `GeneratorEquiv`) — free group machinery,
  reduced word normal form, freeness predicates.
- `Mathlib/Topology/MetricSpace/Isometry.lean` — `IsometryEquiv` structure,
  `Group (α ≃ᵢ α)`, refl / trans / symm.
- `Mathlib/Analysis/InnerProductSpace/PiL2.lean` — `EuclideanSpace`,
  basis, norm. `EuclideanSpace ℝ (Fin 3)` is the ambient space.
- `Mathlib/Geometry/Euclidean/Angle/Unoriented/CrossProduct.lean` — cross
  product on ℝ³ (may help concrete rotation construction).
- `Mathlib/LinearAlgebra/UnitaryGroup.lean` — matrix unitary / orthogonal
  bases. Whether `Matrix.specialOrthogonalGroup` exists is uncertain — confirm
  via Grep before assuming.

**Gap reality check (audit 2026-05-26)** — the following key prerequisites
are **NOT in mathlib** (verified by Grep):

- Free subgroup of `SO(3)` of rank ≥ 2 (`free subgroup SO` / `rotation
  free group` 0 hits).
- Hausdorff paradox (S² paradoxical decomposition under SO(3)) — 0 hits.
- Ping-pong lemma for proving freeness from a group action — 0 hits.
- Banach–Tarski itself (`BanachTarski` / `banach_tarski` 0 hits).

Expect these to be Forwards, not searches that succeed.

## Strategic notes

The proof method is the agents' choice. A canonical textbook route
(Wagon, *The Banach–Tarski Paradox*, ch. 1–3) goes roughly:

1. **`F₂` is paradoxical**: rank-2 free group `F₂ = ⟨a, b⟩` decomposes as
   `{1} ⊔ Wₐ ⊔ Wₐ⁻¹ ⊔ Wᵦ ⊔ Wᵦ⁻¹` (`Wₓ` = reduced words starting with `x`),
   with `a · Wₐ⁻¹ = F₂ \ Wₐ` and similarly for `b`. Pure group theory on
   mathlib `FreeGroup`.
2. **`F₂ ↪ SO(3)`**: build two concrete rotations and prove they generate
   a free rank-2 subgroup. Classical route is the ping-pong lemma; other
   routes exist (e.g. transcendence-based).
3. **Hausdorff paradox on `S²`**: lift the `F₂` decomposition through the
   embedding to a paradoxical decomposition of the sphere modulo a
   countable fixed-point set; absorb the latter via a Hilbert-hotel
   rotation argument.
4. **Sphere → solid ball**: cone construction + handle the origin.

Other routes are welcome — sub-Riemannian / horocycle dynamics, direct
construction via SL₂(ℤ) on hyperbolic plane, or measure-theoretic
contradiction arguments — provided they land on the stated form.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (FreeGroup machinery,
   IsometryEquiv group, Equidecomp base operations, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did
not `Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

Statement-altering moves only — proof route is free.

- **Citing Banach–Tarski as a single mathlib theorem** — confirmed missing
  by audit. If you find a `BanachTarski` hit, surface via `RequestUserAmend`.
- **Changing the acting group** away from `E ≃ᵢ E` (e.g. restricting to
  `SO(3)`) — alters the statement. Surface via `RequestUserAmend` if you
  want to retarget.
- **Replacing closed ball with open ball or with the sphere `S²`** —
  different theorem (Hausdorff paradox is the sphere version).
  Surface via `RequestUserAmend` if you want to retarget.
