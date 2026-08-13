---
problem: Test.codex_probe
---

# Test.codex_probe

A provider smoke test, not a mathematics exercise: one worker spawn
should touch most of its tool surface once and report, in its own
deliverable, what each tool actually answered.

No root goal — the brick below rides the Forward arm, which has no
deterministic pre-pass, so it is guaranteed to reach a worker. (A `True`
root would not: `tactic_try` closes that with zero spawns, which is what
happened to `Test.compute_probe` on 2026-08-11.)

## Statement

A single concrete arithmetic fact: `2 ^ 31` leaves remainder `2` on
division by `7`.

Deliberately a claim about specific numbers rather than a general
lemma. The first version of this problem asked for
`∀ n : ℕ, 2 ∣ n * (n + 1)` and the worker correctly declined it —
Mathlib already carries `Nat.two_dvd_mul_add_one` with the identical
type, so the only right answer was "this already exists" and the
roll-call had nowhere to land. A statement about one concrete value
cannot collide with a named library lemma.

### Deliverables

One landed brick, kernel-checked, no `sorry`:

- `probe_two_pow_31_mod_seven : 2 ^ 31 % 7 = 2`

Settle the right-hand side with `compute` BEFORE proving it (step 1 of
the roll-call). If `compute` disagrees with the number written above,
that is the interesting outcome, not an obstacle: decline `unprovable`
and put the value it actually printed in the note.

`MarkDeliverable` that brick, then `Ingest`.

**Do not decline this deliverable because something like it exists
elsewhere.** For an intermediate brick, "the library already has it" is
the right call and citing beats re-proving. This is not one: it is what
the operator asked for by name, so it is delivered, not adjudicated.

## Tool roll-call — the actual deliverable

The proof is one line and it already exists elsewhere in this tree, so
**landing the brick quickly does not shorten the roll-call** — the
roll-call is what this problem is for. A brick that lands without it has
measured nothing.

Call each tool below **once**, and record what it answered in the brick
file's leading comments, one line each:

    -- <tool> said: <what the tool returned for THIS call, verbatim>

Quote the tool's answer, not the boilerplate it prints on every call:
`compute`, for one, prefixes every result with a standing note about not
being a proof, and that note is not its answer to your question.

If a tool is reached and does not work — an error, a refusal, an
"unavailable" — write

    -- <tool> failed: <the tool's own message, verbatim>

and move to the next one. **That is a result, not a reason to stop**: do
not work around it, do not retry it more than once, and do not do its job
yourself.

A tool you never called is a different thing, and there is no line that
records one. **The roll-call counts as performed only when every line
below quotes something a tool actually returned.** If any tool was never
reached, say so plainly in your submission notes and treat the batch as
incomplete — do not mark the deliverable and do not close the problem on
it.

1. `compute` — run exactly `print(2**31 % 7)`, and record the number it
   printed (this is the deliverable's right-hand side, so the call is
   load-bearing, not ceremony)
2. `loogle` — search for a Mathlib lemma about divisibility of `Nat`
3. `inspect` — read this problem's `Manifest.md`
4. `validate_json` — hand it `{"probe": true}`
5. `goal_at` — on a line INSIDE your proof, where a goal exists (a
   position with no goal answers nothing)
6. `errors_at` — on the brick file you are building
7. `validate_file` — you need it anyway; record its verdict

Then land the brick. Nothing else is in scope: do not generalize the
statement, do not decompose it, do not add hypotheses.

## Strategic notes

One brick, one batch. Keep the Programme to a single Roadmap entry and a
single experiment — the roll-call above IS the experiment.
