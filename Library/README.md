# Library/

Promoted theorems re-exported from `Problems/` proved roots. Organized
by Mathlib-style topic so cross-Problem reuse picks up exactly the
relevant subset.

## Structure

```
Library/
  <Topic>/
    <problem>.lean      # re-export: theorem <problem> := Problems.<problem>.main
    INDEX.md            # human-readable list of topic's contents
```

Files are **framework-managed** — written by cascade hook on root
`status='proved'` (with axiom-whitelist gate). Don't hand-edit; changes
will be overwritten by the next promotion.

## Topics

Mirrors Mathlib's first-level directory layout. Pick the closest match
for each Problem; framework falls back to `Misc` when no topic can be
inferred from the Problem's `lemma_hints`.

- `Algebra/`         — group / ring / field / module / linear algebra
- `Analysis/`        — limits / continuity / derivatives / measure
- `Combinatorics/`   — graph / counting / Ramsey
- `Data/`            — concrete data structures (Nat / Int / List / ...)
- `Geometry/`        — Euclidean / projective / differential
- `Logic/`           — propositional / first-order / type theory
- `MeasureTheory/`   — measures / integration / probability
- `NumberTheory/`    — primes / mod arithmetic / factorials / ZMod
- `Order/`           — orders / lattices / Galois
- `SetTheory/`       — sets / cardinals / ordinals
- `Topology/`        — open / compact / connected / metric
- `CategoryTheory/`  — functors / limits / adjunctions
- `Misc/`            — uncategorized landing zone

## Referencing in a Problem's Manifest

Use the `## Lemma hints` section with `Library.<Topic>.<problem>` paths:

```yaml
## Lemma hints
- Mathlib.NumberTheory.ZMod.Basic
- Library.NumberTheory.wilson
```

Both Mathlib and Library entries flow through the same `lemma_lookup`
pipeline (lake env lean `#check`), so the agent sees their signatures
inline in Context.md.
