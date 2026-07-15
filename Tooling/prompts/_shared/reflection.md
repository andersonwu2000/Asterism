You just finished `{kind}` on `{slug}` (goal id `{goal_id}`, outcome=`{outcome}`) in problem `{problem}`.

Reflect: did this attempt expose an insight that helps a DIFFERENT, unrelated goal in this problem? **Default to `skip`** — that is the dominant outcome. Record a GLOBAL lesson ONLY for a cross-cutting, transferable insight: a Mathlib/Library API gotcha, an instance-resolution trap, a tactic that reliably handles a recurring shape.

NOT a lesson — these are a `skip`:
  - Anything specific to THIS goal `{slug}` (how it decomposed, which sub-goals/lemmas closed it, its model map / witness). It helps no other goal; the decomposition is already recorded mechanically. SKIP.
  - "It was hard" / a vague restatement of the outcome.
  - A framework-internals guess.

Existing global lessons for this problem:

```
{global_lessons}
```

OUTPUT — write your decision as JSON to `{decision_path}`. Exactly one of:
  - `{"action": "skip"}` — no cross-goal-transferable insight (the common case).
  - `{"action": "global_add", "title": "<one-line insight>", "body": "<optional: decls, tactic, exact shapes>"}` — a transferable insight for OTHER goals, AND no entry above already covers it (no duplicates). Rejected at the entry cap (shown above the list) — at capacity use `global_edit` instead.
  - `{"action": "global_edit", "id": <id from the list above>, "title": "<corrected one-liner>", "body": "<optional detail>"}` — an entry above is now false or superseded by this `{outcome}`; or, AT CAPACITY, the least valuable entry your new insight outranks — full overwrite. Not sure it outranks any → `skip`.

`title` is the actionable one-liner; `body` is optional elaboration.

Standing Strategist directive for this problem (separate from the above):

```
{directive}
```

If — and ONLY if — that directive makes a CONCRETE claim this `{outcome}` specifically disproved (e.g. "lemma X exists / is provable" when you just refuted it), retract it: write the one-line reason to `{attempts_dir}/_directive_retract.md`. High bar — "it was just hard" is NOT grounds; when unsure, do not retract. This is independent of your JSON decision.

Time budget: {timeout_min} min. Write the JSON promptly and exit.
