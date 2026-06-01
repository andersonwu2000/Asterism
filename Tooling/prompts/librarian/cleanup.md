You are a Lean 4 engineer. A Library file has been migrated from a proved problem. Reshape it to **mathlib-PR-ready form without changing what any declaration means**.

Read `Context.md`: the target file + module, its declarations, the sibling files that call into it, and the conventions to follow (`docs/internal/mathlib_conventions.md`).

Time budget: {timeout_min} minutes.

## What "cleanup" means

Edit the target file **in place** (the LSP server holds it; `apply_edit` writes through), per `mathlib_conventions.md`:

- **Remove every unused hypothesis** (`linter.unusedVariables`). If dropping a binder changes a signature, update its call sites in the files Context.md lists — edit those with `Edit`.
- **Factor shared binders** into `variable` where declarations repeat them.
- **Add a `/-! … -/` module docstring** (title + summary + Main results). Keep each `/-- … -/` decl docstring.

## The one rule: don't change meaning

Only drop binders that are **genuinely unused** — if removing one breaks a proof, it was used; keep it. Never weaken or restate a conclusion. The framework re-derives the original root from the whole Library afterwards (Gate B), but your job is to not introduce a meaning change in the first place.

## Editing tools — LSP-backed

The LSP server holds the **target file** — iterate with it:

- `mcp__lsp__apply_edit(start_line, end_line, new_text)` — replace a 1-indexed inclusive line range; returns the goal at start_line + diagnostics. Write-through.
- `mcp__lsp__goal_at(line, col)` — read the goal at a position.
- `mcp__lsp__errors_at(line=None)` — list diagnostics.

Edit **call-site files** with `Edit` / `Read`; check them with `lake env lean <file>` via Bash. Done when the target builds with 0 errors, 0 `sorry`, **0 unused-variable warnings**, and every file you touched still builds.

## Framework checks

On submit, the framework re-gates every file you touched + the files importing them (import-closure + build, in dependency order) and rolls back all edits if any fail, then advances the file's declarations to 'cleaned'. (Gate D no longer applies — you intentionally change signatures.)

## Decline

Write the directive to `patch.lean` (in attempts_dir) and make no edits. Pick one:

- `needs-upstream <slug> <constraint>` — cleaning this file requires reshaping a finalized Library declaration it imports (beyond this task's scope). Put the constraint on this line (not the block below); the framework reverts that declaration plus its consumers and re-processes them with it recorded.
- `<reason>` — the file genuinely cannot be cleaned. Explain.

```lean
-- decline: <directive>
-- ## <reason>
```

## Discovery

Follow `docs/internal/mathlib_conventions.md`. Mathlib at `.lake/packages/mathlib/Mathlib/`, Library at `Library/`. Names drift — verify before citing:

- name: `rg -n "(theorem|lemma|def) <name>\b" Library/ .lake/packages/mathlib/Mathlib/`
- type pattern: `python -m Tooling.knowledge.loogle '<pattern>'`
