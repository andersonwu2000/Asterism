# Problems/

Stress-test problem inventory. Each subdir is a `Problem` in the
framework sense (own Manifest / Defs / Root / proofs / TREE / DB row).

## Layout convention

New problems are named `<Domain>.<slug>` and live at
`Problems/<Domain>/<slug>/`. `db.problem_dir` maps the dotted slug to
the nested path automatically (same mechanism the `Minif2f.*` import
batch uses).

Domain dirs:

| Domain | mathlib alignment |
|---|---|
| `Algebra/` | group / ring / commutative algebra / linear algebra / representation theory |
| `Analysis/` | real / complex / functional / Fourier / measure theory |
| `Geometry/` | differential / Riemannian / convex / plane / projective |
| `Topology/` | point-set / algebraic / fixed-point |
| `NumberTheory/` | analytic / algebraic / elementary |
| `Logic/` | model theory / proof theory / set theory |
| `Probability/` | measure-theoretic probability, stochastic processes |
| `Combinatorics/` | graph theory / discrete |
| `Minif2f/` | the miniF2F benchmark import — frozen layout, don't redistribute into the domain dirs |

## Legacy top-level problems (preserved)

These problems were created before the domain convention landed.
They stay at `Problems/<slug>/` rather than being renamed because
their proof artifacts (250+ `.lean` files for `residue_thm`, etc.)
have `namespace Problems.<slug>` and `import Problems.<slug>....`
hard-wired into every file — renaming requires sed-replace across
the whole subtree plus DB `problems.name` / `goals.problem` update,
which is high-risk for already-proved artifacts with low payoff.

| Legacy slug | Proved | Notes |
|---|---|---|
| `residue_thm` | 2026-05-21 | Cauchy Residue Theorem, ~500 goals |
| `pi1_circle` | 2026-05-21 | π₁(S¹) ≅ ℤ, 24 goals |
| `sylvester_gallai` | yes | Sylvester-Gallai (every non-collinear point set has an ordinary line) |
| `proj_nonexpansive` | yes | metric projection onto closed convex set is non-expansive |
| `sl2_v_n_irreducible` | yes | cyclic highest-weight sl₂-module is irreducible |

If a sixth proved problem appears at top-level, add it here. The
domain dirs are the canonical home for everything created from
2026-05-22 onward.

## See also

- `docs/CLAUDE.md` Asterism-specific fact section — Problem naming
  convention and the "don't `git mv` a proof-bearing dir without
  fixing namespace + import + DB" warning.
- `docs/internal/strategy/mathlib_gaps.md` — stress-target catalog (drives
  which domain a new problem lands in).
