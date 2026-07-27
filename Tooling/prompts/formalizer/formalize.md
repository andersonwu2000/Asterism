Work turn. Your goal is in `patch.lean` (locked signature `<kind> s<id> ... := by sorry`). Close it directly, or decompose it along the Programme `## Proof`'s argument into 1-7 strictly simpler sub-goals + a structural combinator — your call, and you may switch mid-turn.

`Context.md` now carries `## Candidate lemmas` (pre-searched, `#check`-verified), FORBIDDEN_LEMMAS, prior failures. Companion files (`PAST_*.md`) carry full failure detail — read on demand. If a prior turn timed out, `## Your previous progress note` is your starting sketch. The `## Proof` carries the claim and its WHY; the Lean shape (ranges, constants, encoding) is yours — keep the claim, fix the form.

Time budget: {timeout_min} minutes.

## Tools — LSP-backed

Four MCP tools talk to a live Lean server holding **your `patch.lean`** (sandboxed in attempts_dir — edits never touch committed files; your final patch.lean + new_*.lean are what the framework commits):

- `mcp__lsp__apply_edit(start_line, end_line, new_text)` — replace a 1-indexed inclusive line range; returns post-edit goal + diagnostics. Persists to `patch.lean`.
- `mcp__lsp__goal_at(line, col)` — read the proof goal at any position.
- `mcp__lsp__errors_at(line=None)` — list current diagnostics.
- `mcp__lsp__validate_file(content)` — elaborate a *standalone* candidate (auto-prepends Mathlib + Defs + your patch's `open`s). Beyond `diagnostics` it returns a `submission` block mirroring the commit gates — treat a `submission` error as a commit blocker even when `ok:true`. Run it on each `new_<slug>.lean`, and on `patch.lean` before finishing.

## Path A — direct proof

Replace `:= by sorry` with a tactic block; ship `patch.lean` alone (no `new_*.lean`). Iterate with apply_edit/goal_at until 0 errors, 0 sorry. Citing a **proved** sibling is allowed — write its import yourself (`import Problems.<problem>.proofs.L_<slug>`); the submission is axiom-probed.

## Path B — decompose

1. **Sketch**: apply_edit the body into a candidate skeleton:
   ```
     intro ...
     have h_<slug_1> : <stmt_1> := by sorry
     have h_<slug_2> : <stmt_2> := by sorry
     exact <combinator> h_<slug_1> h_<slug_2>
   ```
2. **Check**: errors_at — only sorry warnings → each sub-claim type-checks AND the combinator closes the goal. Revise until clean.
3. **Cite**: for each sub-claim, grep Mathlib + scan proved siblings / Library / `## Lessons learned` for a direct replacement — one less sub-goal to register.
4. **Prove-in-place**: a sub-claim you can close right now with a short tactic block needs no stub — prove it inline in the body.
5. **Stub**: each remaining sub-claim becomes `new_<slug>.lean` in attempts_dir; `validate_file` each:
   ```lean
   namespace Problems.<problem>

   theorem <slug> : ... := by sorry

   end Problems.<problem>
   ```
   `<slug>`: `[a-z][a-z0-9_]*`, ≤ 60 chars, descriptive; theorem name MUST equal the slug in the filename; framework auto-suffixes collisions. Stub only — the sub-goal's annotation is written by whoever closes it.
6. **Link**: final apply_edit on `patch.lean` — once a stub is on disk, reference `<slug> <args>` directly and replace every `have ... := by sorry` placeholder. Without this, patch.lean ships sorry → main inherits sorryAx.

Sub-goals can be parallel (`exact <combinator> h1 h2`) or sequential; `obtain` / `rcases` / `induction` shapes all work.

## Annotation

Before finishing, add a `--` comment block above the theorem (above or below its `set_option ... in` lines) — first non-blank line is the one-line summary (key lemma family / decomposition shape + why it closes the goal). Fix remaining warnings (e.g. lines >100 chars) while there.

## Decline

Place the directive immediately above the theorem in `patch.lean`, keep `:= by sorry`, write no sub-goal files. Pick one:

- `unprovable` — false in this hypothesis scope. Description must give a counterexample (specific values + arithmetic check).
- `return_to_parent` — the goal statement you were handed is incomplete/wrong (parent's decomposition omitted a hypothesis or gave the wrong substructure); provable only once the parent re-states it. Name the missing piece.
- `shelve` — missing vocabulary / theorems / abstractions to proceed (describe the missing piece and how you'd use it), or the goal embeds a large concrete data structure that would replicate across every sub-goal (propose a `def` factoring it out + the signature). In doubt vs `return_to_parent`, pick `shelve`.
- `no_nl_correspondence` — closing this needs mathematics the Proof does not argue (discovered mid-work; intake handles the readable-up-front case). Name what's unbacked.

```lean
-- decline: <directive>
-- ## ...description...
theorem s<id> ... := by sorry
```

## Stop signals

Ship the moment you catch yourself:

- A sub-claim resisting a 3rd distinct tactic approach → stub it (Path B) and ship the decomposition. Wrong types compile-fail in seconds — cheaper than your grinding.
- Pivoting decomposition shape a 3rd time → ship the best one.
- Both paths exhausted → decline with the directive that fits.

## Rules

- Each sub-goal must be **strictly simpler** and as abstract as possible, and do real work — re-stating the parent, or a split one existing lemma closes in one step, does not count. Bundling adjacent steps into one intermediate lemma is fine. Routine expansion of the Proof's argument (algebra, casts, monotonicity, estimates) is yours; a sub-goal carrying mathematics the Proof does not argue is not.
- Each sub-goal is a stand-alone Lean theorem — re-declare any parent binder its type uses or that its own sub-goals will thread. When unsure, keep — over-keeping is mild bloat, dropping a future-needed binder is a wasted attempt.
- Edit only the body of `patch.lean` — signature changes are rejected as `patch_signature_mismatch`. Framework auto-prepends `import Mathlib` + `Defs` and auto-appends sub-goal imports; the ONE import you write yourself is a cited existing sibling's.
- **Citing an existing sibling** (Path B may cite any status; Path A proved only). Framework classifies by status: **proved** → used directly; **open / attempting / pending_review** → auto-linked, your strategy waits for it; **shelved** → auto-revived + linked; **dead / disproved** → rejected — re-declare the statement fresh as your own `new_<slug>.lean` instead.
- A redundant sub-goal file must be deleted from attempts_dir, not commented out.

## Lemma discovery

`## Candidate lemmas` (Context.md) first — pre-searched and `#check`-verified. To find more, Mathlib is at `.lake/packages/mathlib/Mathlib/`; names drift across versions (`pow_le_pow_left` → `pow_le_pow_left₀`), so verify before citing:

- name / notation: Grep over `.lake/packages/mathlib/Mathlib/` (pattern `(theorem|lemma) <name>\b`)
- type pattern: `python -m Tooling.knowledge.loogle '<pattern>'`

## Hard rules

- Do NOT use any name in FORBIDDEN_LEMMAS — anywhere.
- Verify every lemma reference before citing: Grep by name/symbol, loogle by type pattern.
