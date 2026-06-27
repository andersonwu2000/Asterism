You just finished `{kind}` on `{slug}` (goal id `{goal_id}`, outcome=`{outcome}`) in problem `{problem}`.

Reflect: did this attempt expose a signal worth recording for a future agent? **Default to `skip`** — record only what is concrete (names a lemma / API / namespace / goal shape / sibling decl — never a framework-internals guess) and non-obvious (a fresh agent would otherwise re-discover it the hard way).

Two kinds of experience:
  - **Node** — specific to THIS goal `{slug}`: how it decomposes, which sub-goals / lemmas / sibling proofs worked, which route is a dead end. Helps a later attempt on this same goal. Most recordable signals are node; it is append-only (short-lived, never edited).
  - **Global** — a cross-cutting insight for OTHER, unrelated goals in this problem: a Mathlib/Library API gotcha, an instance-resolution trap, a tactic that reliably handles a recurring shape.

Existing global experiences for this problem:

```
{global_lessons}
```

OUTPUT — write your decision as JSON to `{decision_path}`. Exactly one of:
  - `{"action": "skip"}` — no signal (the common case).
  - `{"action": "node", "title": "<one-line lesson>", "body": "<optional: decls, tactic, exact shapes>"}` — a signal for this goal.
  - `{"action": "global_add", "title": "<one-line insight>", "body": "<optional detail>"}` — ONLY if it helps a DIFFERENT goal AND no entry above already covers it (no duplicates).
  - `{"action": "global_edit", "id": <id from the list above>, "title": "<corrected one-liner>", "body": "<optional detail>"}` — an entry above is now false or superseded by this `{outcome}`. No count cap; global experience evolves by editing.

`title` is the actionable one-liner; `body` is optional elaboration.

Standing Strategist directive for this problem (separate from the above):

```
{directive}
```

If — and ONLY if — that directive makes a CONCRETE claim this `{outcome}` specifically disproved (e.g. "lemma X exists / is provable" when you just refuted it), retract it: write the one-line reason to `{attempts_dir}/_directive_retract.md`. High bar — "it was just hard" is NOT grounds; when unsure, do not retract. This is independent of your JSON decision.

Time budget: {timeout_min} min. Write the JSON promptly and exit.
