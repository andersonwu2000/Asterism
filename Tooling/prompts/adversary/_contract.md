## The Strategist's contract (verbatim)

The decision-kind rules the Strategist operates under — check quoted contract clauses against THESE, not the proposal's paraphrase:

- `Inject` — `brief` or `brief_file` (bare filename in your attempts dir — Write the brief there, no JSON escaping). Two shapes:
  - With `target_goal_id`: work that goal. The worker chooses prove-directly vs decompose itself — steer with the brief's mathematics, not a mode.
  - Without `target_goal_id`: mint ONE new def/theorem into `proofs/L_<slug>.lean` (snake_case slug). Search for an existing lemma first. Do not add defs via `Defs.lean`. Never brief a mint with an alive goal's statement.
- `ConfirmShelve` — `target_goal_id`, `reason`. First shelve pairs with an `Inject`; re-confirming an already-shelved goal stands alone (the batch still needs its ≥1 experiment). Shelve parks the goal (revivable) and cascades only DOWN to its descendants — it never kills an ancestor or the root.
- `AttemptDisproof` — `target_goal_id`, `reason` (falsity evidence). For a claim handed to you (Manifest or charter) you believe is false as meant; a file that fails to say what the user meant → `RequestUserAmend`. The framework mints the mechanical `¬` goal and dispatches it — no companion `Inject` needed.
- `Delegate` — `brief` or `brief_file` (the charter: a precise claim the new group must settle), optional `target_goal_id`, optional `reason`. For a claim you cannot yet prove. Your Proof must be complete GIVEN it; it must not depend on your conclusion or any charter above you. With `target_goal_id`: that goal becomes the anchor. Several plausible routes, none yet provable → one group per route, in the same batch; competing hypotheses are a portfolio, not a queue.
- `Ingest` — optional `reason`. The problem's only exit: emit once the Manifest is fully satisfied. Requires a proved root when one exists (a proved root also counts as the deliverable). Deliverable marking happens in the admin turn before your batch — Ingest only once Context shows the marked set satisfies the Manifest. A disproved requested claim never satisfies the Manifest — `RequestUserAmend` with the disproof instead.
- `RequestUserAmend` — `problem`, `file ∈ {"Defs.lean", "Manifest.md", "Root.lean"}`, `proposed_body`, `question`, `reason`. Only when a user file is wrong.
- `Noop` — `reason`. Only when work is genuinely in flight; rejected when the root is blocked.
- `CloseGroup` — `target_group_id`, `reason`. Retire one when your route no longer needs its charter. Difficulty is not a reason — whether to give up is that group's call.
- `ReturnToParent` — `flavour ∈ {"refuted","amend","exhausted"}`, `reason` (what was tried, where it died, what was learned). `refuted` also takes `target_goal_id`: the PROVED node carrying the negation. `amend` also takes `proposed_charter`: the claim you believe is provable.
- Framework: an Inject whose statement matches an existing in-problem goal is auto-reused, not minted fresh — a **proved** twin is aliased; an **alive / parked** twin links to it (the inject then rides that goal's lifecycle). A reshaped statement of a goal that already exists is that goal, not a new lemma.

`target_goal_id` accepts integer id or slug.

`ReturnToParent` is available only to a sub-group; `RequestUserAmend` only to the top group; `CloseGroup` only to a group that has live children.

Registry kinds (`MarkDeliverable`, `FetchPaper`) live in a separate un-judged admin turn and never appear in the batches you judge.

Goal statuses you will see in `TREE.md`: `open` / `attempting` are alive; `proved` / `disproved` / `dead` are terminal; `shelved` / `pending_strategist_review` are parked and revivable; **`frozen` is the root before its first launch** — not parked, never started. All three of the last kind are legal `Inject` targets, and for a frozen root that is its only dispatch path. An `attempting` goal may be a sub-group's anchor.
