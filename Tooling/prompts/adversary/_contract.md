## The Strategist's contract (verbatim)

The decision-kind rules the Strategist operates under — check quoted contract clauses against THESE, not the proposal's paraphrase:

- `Inject` — `proof`. This brick's `Theorem.` statement and `Proof.` argument, copied from this batch's `## Proof` with the vocabulary it uses. The worker formalizes the Theorem against the Proof; it does not read the rest. Three shapes:
  - With `target_goal_id`: work that goal. The worker chooses prove-directly vs decompose itself.
  - Without `target_goal_id`: mint ONE new def/theorem into `proofs/L_<slug>.lean` (snake_case slug); a definition brick writes `Definition.` in place of `Theorem.`, no `Proof.`. Search for an existing lemma first. Do not add defs via `Defs.lean`. Never mint an alive goal's statement.
  - With `target_goal_id` and a counterexample in `proof`: refute that goal. The worker proves the negation, the kernel certifies it, the goal becomes `disproved` and the negation lands as `<slug>_disproof`. Never mint `¬claim` by hand.
- `ConfirmShelve` — `target_goal_id`, `reason`. First shelve pairs with an `Inject`; re-confirming an already-shelved goal stands alone. Shelve parks the goal (revivable) and cascades only DOWN to its descendants — it never kills an ancestor or the root.
- `Delegate` — `charter`, `reason`, optional `brief`, optional `target_goal_id`. Dispatches sub-groups:
    `charter` — the kernel-checkable research item this group exists to settle.
    `reason` — why you cannot prove this yourself and `Inject` it, nor pace it through AHEAD batch by batch — why it must be a group's burden.
    `brief` — guidance and lessons for the group.
  A batch delegates several groups or none — never exactly one; delegation stops two levels below the top. With `target_goal_id`: that goal becomes the anchor.
- Papers are fetched with your tools, not with a decision: `paper_search` resolves a citation to open copies, `paper_fetch` downloads, shelves and binds one to this problem — during this wake, before investing in an unknown or uncertain plan. Do not formalize literature except where necessary.
- `MarkDeliverable` — `target_goal_id`, `reason`. Marks a PROVED brick as one of the claims the charter asks for. Top-level claims only; vocabulary and internal lemmas are never deliverables. The marked set is what `Ingest` is checked against.
- `Ingest` — `report`, optional `reason`. The problem's only exit: emit once the marked set fully satisfies the charter. With a root: the proved root — or the `disproved` root, which closes the problem as `refuted`. `RequestUserAmend` only for a claim the user wrote wrong. `report`: a short paper in English markdown, LaTeX for math, written for a mathematician who has never seen this system — no framework words (goal, brick, batch, Programme). Sections, in this order: `## Introduction` (the question and why it matters), `## Main Result` (the statement as proved, or the counterexample), `## Proof Sketch` (the route in prose, citing the formal lemma names in backticks where a reader would look them up), `## What Remains` (what was refuted or left open). It becomes `REPORT.md`.
- `RequestUserAmend` — `problem`, `file ∈ {"Defs.lean", "Root.lean", "charter"}`, `proposed_body`, `question`, `title`, `reason`. `title`: one line naming the ask. Only when a user file — or the problem's charter (the top group's goal) — is wrong. The user's word is never amendable.
- `CloseGroup` — `target_group_id`, `reason`. Retire one when your route no longer needs its charter; its own sub-projects close with it. Difficulty is not a reason — whether to give up is that group's call.
- `ReturnToParent` — `flavour ∈ {"refuted","amend","exhausted"}`, `reason` (what was tried, where it died, what was learned). `refuted` also takes `target_goal_id`: the `<slug>_disproof` brick the gate minted for a node in your chain. `amend` also takes `proposed_charter`: the claim you believe is provable.
- Framework: an Inject whose statement matches an existing in-problem goal is auto-reused, not minted fresh — a **proved** twin is aliased; an **alive / parked** twin links to it (the inject then rides that goal's lifecycle). A reshaped statement of a goal that already exists is that goal, not a new lemma.
- Framework behaviour is quoted, not inferred — a prompt rule, a gate message, or the directive. Unsourced, it is not a fact.


`target_goal_id` accepts integer id or slug.

Standing rules the batch itself must satisfy — same source, same words:

- Every Inject is proven in the Proof — inject only what is fully argued; anything short of rigorous closure stays in AHEAD awaiting a later batch.
- A batch must not leave your group idle: after it commits, something of yours is in flight, dispatched, or delivered.
- Same-batch Injects must be independent (concurrent dispatch); one that waits, even through a parked goal, stays `ConfirmShelve`d for the next batch.
- The mathematics — claims, arguments, lemma names, invariant constructions, proof techniques — is yours. Tactics, Lean syntax, statement shape (ranges, off-by-ones, constants) are the worker's.

`ReturnToParent` is available only to a sub-group; `RequestUserAmend` only to the top group; `CloseGroup` only to a group that has live children; `Delegate` only to the top group and its direct sub-groups — the group tree caps two levels below the top.

Goal statuses you will see in `TREE.md`: `open` / `attempting` are alive; `proved` / `dead` are terminal; `disproved` is parked on a CLAIMED counterexample — an `Inject` on it revives it when the plan argues the claim is true after all; `shelved` / `pending_strategist_review` are parked and revivable; **`frozen` is the root before its first launch** — not parked, never started. All four parked kinds are legal `Inject` targets, and for a frozen root that is its only dispatch path. An `attempting` goal may be a sub-group's anchor.
