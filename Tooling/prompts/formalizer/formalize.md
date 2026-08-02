Your goal is in `patch.lean` (locked signature `<kind> s<id> ... := by sorry`). Prove it.

`## Proof` argues the claim; formalize it in Lean — keep the claim, the Lean shape is yours.

`Context.md` carries `## Candidate lemmas`, FORBIDDEN_LEMMAS, and failure records; `PAST_*.md` has full failure detail, read on demand. If your prior turn timed out, read `## Your previous progress note`.

Time budget: {timeout_min} minutes.

## Write the proof

apply_edit `patch.lean`'s `:= by sorry` into a tactic block; iterate to 0 errors, 0 sorry. Edit only the body — signature changes are rejected as `patch_signature_mismatch`. The framework auto-prepends `import Mathlib` + `Defs` and auto-appends sub-goal imports.

Four MCP tools talk to a live Lean server already holding **your `patch.lean` sandbox**:

- `mcp__lsp__apply_edit(start_line, end_line, new_text)` — replace a 1-indexed inclusive line range; returns the post-edit goal + diagnostics.
- `mcp__lsp__goal_at(line, col)` — read the proof goal at any position.
- `mcp__lsp__errors_at(line=None)` — list current diagnostics.
- `mcp__lsp__validate_file(content)` — elaborate a standalone candidate (auto-prepends Mathlib + Defs + your patch's `open`s); returns two independent verdicts: `diagnostics` = Lean compilation, `submission` = commit-gate rehearsal — both must be clean (`ok:true` covers only the former). Run it on `patch.lean` too before finishing.

## Outsource the heavy parts

Don't sink the turn into a single sticking point. Outsource on any of:

- It is mechanical and self-contained, yet takes a long stretch of detailed formalization to close.
- It is a free-standing, reusable lemma — worth its own name.
- Closing it needs machinery of its own: induction, heavy case analysis, another domain's tools.

Before outsourcing, check there is no existing replacement. Every outsourced sub-goal must be **strictly simpler** and as abstract as possible. Routine expansion of the argument is your job; bundling adjacent steps into one intermediate lemma is fine, but a sub-goal may not merely restate this goal or an unproved ancestor, and may not carry mathematics the Proof does not argue. Stub only what you will not prove this session; a step you can close yourself goes in `patch.lean` as a `have`, not a stub.

To outsource:

- **Validate the skeleton first**: placeholder each outsourced sub-goal with `:= by sorry` —
  ```
    intro ...
    have h_<slug_1> : <stmt_1> := by sorry
    obtain ⟨N, hN⟩ : ∃ N, <stmt_2> := by sorry
    exact <combinator> h_<slug_1> hN
  ```
  errors_at shows only sorry warnings ⇒ every sub-goal type-checks AND the rest of the proof closes the parent goal. Not clean → fix the skeleton. The placeholder is a validation device, not `have`-only; sub-goals may be parallel (as above) or sequential.
- **Write stubs**: one `new_<slug>.lean` per sub-goal in attempts_dir, `validate_file` each:
  ```lean
  namespace Problems.<problem>

  theorem <slug> : ... := by sorry

  end Problems.<problem>
  ```
  `<slug>`: `[a-z][a-z0-9_]*`, ≤ 60 chars, descriptive; the theorem name MUST equal the slug in the filename. Delete any file you change your mind about.
- **Re-declare binders**: each sub-goal is a stand-alone Lean theorem — re-declare every parent binder its type uses or its own sub-goals will thread; when unsure, keep.
- **Link**: one final apply_edit on `patch.lean` — once a stub is on disk, reference `<slug> <args>` directly, replacing every sorry placeholder:
  ```
    have h_<slug_1> : <stmt_1> := <slug_1> <args>
    obtain ⟨N, hN⟩ := <slug_2> <args>
    exact <combinator> h_<slug_1> hN
  ```
  `Unknown identifier` means that stub file isn't written yet. Skip this step and patch.lean ships sorry — main inherits sorryAx.

patch.lean + new_*.lean are the deliverable; outsourced sub-goals are registered as independent nodes and advance in parallel.

## Lemma discovery

Never use any name in FORBIDDEN_LEMMAS.

`## Candidate lemmas` (Context.md) first — pre-searched and `#check`-verified — then scan proved siblings / Library / `## Lessons learned`. For more, Mathlib is at `.lake/packages/mathlib/Mathlib/` (names drift across versions; verify before citing) — Grep (`(theorem|lemma) <name>\b`) or `loogle('<pattern>')`.

**Citing an existing sibling**: write the import yourself (`import Problems.<problem>.proofs.L_<slug>`, one line each). Any sibling except **dead / disproved** — re-declare those fresh as your own `new_<slug>.lean` instead. Citing a not-yet-proved sibling is a legitimate delivery: the framework records the dependency. What you may not cite: your own ancestor, or a statement equivalent to this goal (or an unproved ancestor).

## Annotation

Before finishing, add a `--` comment block above the theorem (above or below its `set_option ... in` lines) — first non-blank line is the one-line summary (key lemma family / decomposition shape + why it closes the goal). Fix remaining warnings (e.g. lines >100 chars) while there.

## Decline

When one of the cases below applies, place the directive immediately above the theorem in `patch.lean`, keep `:= by sorry`, write no sub-goal files. Pick one:

- `unprovable` — false in this hypothesis scope. The description must give a counterexample (concrete instance + a check of the logic).
- `return_to_parent` — the goal statement you were handed is incomplete/wrong (parent's decomposition omitted a hypothesis, gave the wrong structure, …); provable only once the parent re-states it. Name the missing piece.
- `shelve` — missing vocabulary / theorems / abstractions to proceed (describe the missing piece and how you'd use it), or the goal embeds a large concrete data structure that would replicate across every sub-goal (propose a concrete shape). In doubt vs `return_to_parent`, pick `shelve`.
- `no_nl_correspondence` — closing this needs mathematics the Proof does not argue. Name what's unbacked.

Make the description actionable, e.g.:

```lean
-- decline: return_to_parent
-- ## Fix hint
-- Parent passes hmin (b,pt,r) and hmin (a,pt,r); needs hmin (r,a,pt) — without it
-- h1+h2 are simultaneously satisfiable.
theorem s<id> ... := by sorry
```
