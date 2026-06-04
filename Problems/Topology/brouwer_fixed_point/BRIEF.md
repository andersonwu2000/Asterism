# Topology.brouwer_fixed_point — BRIEF

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
- sperner*
- Sperner*
- kuhn*
- Kuhn*
- simplicial_label*
- barycentric_label*
- rainbow_label*

## Strategic notes (from Manifest.md)
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
