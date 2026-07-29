Produce **one** new brick that strengthens the project's library, from the Strategist's brief (`## Strategist brief` in Context.md; `## Library` lists proved lemmas, past Forward proposals surface prior mints).

The brief either pins an explicit statement — ship it as written (rename only to satisfy the slug rule) — or states a claim / direction and you design the statement: **generic** (useful across multiple Goals) and **argued in the Proof**. A claim restated from the Programme Proof is pinned mathematics; the Lean shape (ranges, constants, encoding) is yours — keep the claim, fix the form.

Time budget: {timeout_min} minutes.

## Tools — LSP-backed

Live Lean server holds **your `new_forward.lean`** (pre-seeded with `import Mathlib` + `Defs` + the problem `namespace`; sandboxed in attempts_dir — your final edit is what the framework commits):

- `mcp__lsp__apply_edit(start_line, end_line, new_text)` / `goal_at(line, col)` / `errors_at(line=None)` — edit, read a goal, list diagnostics.
- `mcp__lsp__validate_file(content)` — elaborate a standalone candidate; a leading `sorry` is OK.

Write your declaration (with its leading `-- Forward rationale:` comment) into the namespace body, then validate until only sorry warnings remain.

## Output: one declaration in new_forward.lean

| Brief asks for | Use |
|---|---|
| A proposition to prove (any Prop) | `theorem <slug> : <type> := by sorry` |
| A value, function, or construction | `def <slug> (...) : <return type> := <body>`; unfinished → `noncomputable def <slug> : <Type> := sorry` (explicit type required) |
| A composite type bundling fields | `structure <slug> where ...` |
| An abstract interface | `class <slug> (α : Type) where ...` |
| A new inductive type | `inductive <slug> : <Type> where ...` — complete, no `sorry` |
| A typeclass instance | `instance <slug> : <Class> where ...` — named, no priority group |

```lean
namespace Problems.<problem>

-- Forward rationale: <why this brick, what gap it fills>
theorem <slug> : <type> := by sorry

end Problems.<problem>
```

- `<slug>`: `[a-z][a-z0-9_]*`, ≤ 60 chars, descriptive. Read from the declaration head, not the filename. A slug colliding with an existing `proofs/L_*.lean` hard-fails the commit — pick a fresh name (Grep `proofs/` if unsure).
- `Forward rationale:` is required — it ships in the brick's file header as the permanent record of why it exists.
- Keep the seeded imports; add `import` lines only to cite proved siblings or Library modules.
- Proof body optional; if included it must be sorry-free and `validate_file`-clean.

## Decline

If after reading Library / Mathlib / brief you believe **the brick already exists** — a Library/Mathlib lemma, a proved sibling, or an ALIVE in-problem Goal (name its slug; closing an existing goal is not mint work) — edit `new_forward.lean` to a decline placeholder:

```lean
namespace Problems.<problem>

-- decline: library_sufficient
-- ## Why
-- Brief asked for X; `<existing_lemma_name>` already states exactly this (verified via Grep).
theorem _forward_decline : True := by trivial

end Problems.<problem>
```

## Stop signals

Ship as `:= by sorry` the moment a proof attempt doesn't close on the first try or you're picking specific values / case orderings. Type-check via `validate_file` and exit.

## Rules

- One brick per invocation. Edit only `new_forward.lean` — do NOT create other `new_*.lean` files.
- A statement matching an alive in-problem Goal (`## Alive goals` in `CATALOG.md`) never lands: decline and name the goal.
- When the problem ships `Defs.lean`: `def` / `structure` / `class` slugs must NOT match a symbol referenced in the user's Manifest statement — statement-vocabulary belongs in user-owned `Defs.lean`.

## Lemma discovery

Never use any name in FORBIDDEN_LEMMAS.

Mathlib is at `.lake/packages/mathlib/Mathlib/`; names drift across versions (`pow_le_pow_left` → `pow_le_pow_left₀`), so verify every reference before citing:

- name / notation: Grep (pattern `(theorem|lemma) <name>\b`)
- type pattern: `python -m Tooling.knowledge.loogle '<pattern>'`
