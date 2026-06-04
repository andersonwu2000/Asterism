# Geometry.banach_tarski — BRIEF

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

## Library available (reusable — proved in prior Problems)

Theorems Asterism already proved and harvested into `Library/`. **Prefer citing these over re-deriving.** To use one: `import <module>` (the dotted prefix before the decl's last component) and reference it by its full name. You have read access to `Library/` — grep there for exact signatures. The R1 search-before-reconstruct rule covers Library too.

Library modules in the `Geometry` domain (grep `Library/` for signatures):
- **Geometry.banach_tarski** (155 decls) — keystone `Library.Geometry.BanachTarski.Equidecomp.main`
