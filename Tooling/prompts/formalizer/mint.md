Produce **one** new brick to the `## Strategist brief`'s specification — keep the claim, the Lean shape is yours.

Before minting, grep Mathlib + Library + siblings to confirm the brick does not already exist.

Time budget: {timeout_min} minutes.

## Tools — LSP-backed

`new_forward.lean` comes pre-seeded with `import Mathlib` + `Defs` + the problem `namespace`; your final edit of it is what the framework commits.

Four MCP tools talk to a live Lean server already holding **your `new_forward.lean` sandbox**:

- `mcp__lsp__apply_edit(start_line, end_line, new_text)` / `goal_at(line, col)` / `errors_at(line=None)` — edit, read a goal, list diagnostics.
- `mcp__lsp__validate_file(content)` — elaborate a standalone candidate; a leading `sorry` is OK.

Write your declaration into the namespace body, then validate until only sorry warnings remain.

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

theorem <slug> : <type> := by sorry

end Problems.<problem>
```

- Edit only `new_forward.lean`, one declaration per invocation — do NOT create other `new_*.lean` files.
- `<slug>`: `[a-z][a-z0-9_]*`, ≤ 60 chars, descriptive. Read from the declaration head, not the filename. A slug colliding with an existing `proofs/L_*.lean` hard-fails the commit — pick a fresh name (Grep `proofs/` if unsure).
- When the problem ships `Defs.lean`: `def` / `structure` / `class` slugs must NOT take a symbol name the Manifest statement references — statement vocabulary belongs to the user-owned `Defs.lean`.
- Keep the seeded imports; add `import` lines only to cite proved siblings or Library modules.
- If the proof is easy, prove it directly — it must then be sorry-free and `validate_file`-clean.

## Decline

When one of the cases below applies, turn `new_forward.lean` into the decline placeholder. Pick one:

- `library_sufficient` — the brick already exists: a Library/Mathlib lemma, a proved sibling, or an ALIVE in-problem Goal (check `## Alive goals` in `CATALOG.md` and name it; closing an existing goal is not mint work).
- `missing_prereq` — vocabulary / definitions / abstractions needed to state this brick are missing — if you can state it, sorry-stub it; decline only when you cannot. Describe the missing piece and how you'd use it.
- `unprovable` — false in this hypothesis scope. The description must give a counterexample (concrete instance + a check of the logic).

Make the description actionable, e.g.:

```lean
namespace Problems.<problem>

-- decline: missing_prereq
-- ## Why
-- The statement minimises `line_dist_sq`, but that def has not landed; this
-- brick's type is only writable once it does.
theorem _forward_decline : True := by trivial

end Problems.<problem>
```

## Stop signals

Ship as `:= by sorry` the moment a proof attempt doesn't close on the first try or you're picking specific values / case orderings. Type-check via `validate_file` and exit.

## Lemma discovery

Never use any name in FORBIDDEN_LEMMAS.

Mathlib is at `.lake/packages/mathlib/Mathlib/` (names drift across versions; verify before citing) — Grep (`(theorem|lemma) <name>\b`) or `loogle('<pattern>')`.
