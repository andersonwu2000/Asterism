Your goal is in `patch.lean` (locked signature `<kind> s<id> ... := by sorry`). Prove it.

`## Proof` argues the claim; formalize it in Lean — keep the claim, the Lean shape is yours.

`Context.md` carries `## Candidate lemmas`, FORBIDDEN_LEMMAS, and failure records; `PAST_*.md` has full failure detail, read on demand. If your prior turn timed out, read `## Your previous progress note`.

Time budget: {timeout_min} minutes.

## Write the proof

apply_edit `patch.lean`'s `:= by sorry` into a tactic block; iterate to 0 errors, 0 sorry. Edit only the body and the annotation block above the theorem — signature changes are rejected as `patch_signature_mismatch`. The framework auto-prepends `import Mathlib` + `Defs` and auto-appends sub-goal imports.

Four MCP tools talk to a live Lean server already holding **your `patch.lean` sandbox**:

- `mcp__lsp__apply_edit(edits)` — anchored edits, several per call: `[{"replace": "<exact old text>", "with": "<new>"}, {"replace_between": ["<from>", "<to>"], "with": "<new>"}, {"insert_after": "<anchor>", "text": "<new>"}]`. Anchors must be verbatim and unique; if one fails NOTHING is applied and the response says which and how to fix it. No line numbers — the response reports where each edit landed, plus the file’s tail and `scope_balance`.
- `mcp__lsp__goal_at(line, col)` — read the proof goal at any position.
- `mcp__lsp__errors_at(line=None)` — list current diagnostics.
- `mcp__lsp__validate_file()` — validate `patch.lean` from DISK; `file="new_<slug>.lean"` validates a stub (auto-prepends Mathlib + Defs + your patch's `open`s). Returns two independent verdicts: `diagnostics` = Lean compilation, `submission` = commit-gate rehearsal — both must be clean (`ok:true` covers only the former). Write first, then validate — there is no string mode, and commit checks it saw your final bytes. Run it once more before finishing.
- `mcp__lsp__withdraw_stub(slug)` — drop a `new_<slug>.lean` you no longer want submitted as a sub-goal.
- `inspect([{"grep":"Bar","in":"proofs/*.lean"},{"decl":"foo"}])` — several read questions in one call; `decl` answers from the framework's record. `compute(code)` runs a Python calculation (numpy; no filesystem, no network — and it proves nothing, only the Lean kernel does).

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
- **Write stubs**: one `new_<slug>.lean` per sub-goal in attempts_dir, `validate_file(file="new_<slug>.lean")` each:
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

Goal known but name unknown: `have h : <stmt> := by exact?` then validate_file — diagnostics return Lean's `Try this: exact <name> ...`; substitute it. Keep the statement in standard shape (`f + g`, not `fun n => f n + g n`); big goals can time out — fall back to Grep/loogle.

**Citing an existing sibling**: write the import yourself (`import Problems.<problem>.proofs.L_<slug>`, one line each). Any sibling except **dead / disproved** — re-declare those fresh as your own `new_<slug>.lean` instead. Citing a not-yet-proved sibling is a legitimate delivery: the framework records the dependency. What you may not cite: your own ancestor, or a statement equivalent to this goal (or an unproved ancestor).

## Annotation

When the proof stands (0 errors, 0 sorry — warnings don't block the proof loop): replace the `-- STRATEGY: replace me` line above the theorem with your annotation — first non-blank line is the one-line summary (key lemma family / decomposition shape + why it closes the goal). An unreplaced placeholder counts as no annotation. Fix remaining warnings (e.g. lines >100 chars) while there.

## Decline

When one of the cases below applies, place the directive immediately above the theorem in `patch.lean`, keep `:= by sorry`, write no sub-goal files. Pick one:

- `disprove` — you believe the statement is FALSE: rewrite the goal statement in `patch.lean` to `¬ (<the locked signature's statement>)` (or its push_neg form) and prove it — the one exception to "keep `:= by sorry`". If you cannot prove the negation, use `return_to_nl`.
- `return_to_parent` — the goal statement you were handed is incomplete/wrong (parent's decomposition omitted a hypothesis, gave the wrong structure, …); provable only once the parent re-states it. Name the missing piece.
- `shelve` — missing vocabulary / theorems / abstractions to proceed (describe the missing piece and how you'd use it), or the goal embeds a large concrete data structure that would replicate across every sub-goal (propose a concrete shape). In doubt vs `return_to_parent`, pick `shelve`.
- `return_to_nl` — the argument you were given does not settle this goal: uncovered, mis-aimed, or false as stated. Name which, and what. Do not reroute around it.

Make the description actionable, e.g.:

```lean
-- decline: return_to_parent
-- ## Fix hint
-- Parent passes hmin (b,pt,r) and hmin (a,pt,r); needs hmin (r,a,pt) — without it
-- h1+h2 are simultaneously satisfiable.
theorem s<id> ... := by sorry
```
