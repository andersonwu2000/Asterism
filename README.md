# Asterism

<!-- Add your project overview here. -->

## Install

**Windows — no terminal, ever:**

1. Get this folder (download & unzip, or clone).
2. Double-click **`Asterism.exe`** — the one door. On a fresh machine
   your browser opens a setup page that detects what's already there
   and installs the rest with one button — Python, the engine, Git,
   the Lean prover (or adopts one you already have), the multi-GB
   math library, and Claude Code. Each target shows live progress in
   a checklist; the only step that needs you is the one-time Claude
   login (a browser tab opens — click Authorize). When it's all green
   the page hands off to the Asterism console by itself. Every day
   after, the same exe (or the Desktop shortcut it creates) opens the
   console directly. Then: create a problem, press Run.

   (If Windows SmartScreen objects to a downloaded copy: More info →
   Run anyway. AV blocking the exe entirely? Right-click
   `installer\setup-server.ps1` → Run with PowerShell, then open
   http://127.0.0.1:8641/ in your browser.)

Re-running the exe is always safe; if anything is missing or broken it
reopens the setup page, and finished parts are skipped. (`Asterism.exe`
is a ~5 KB stub compiled from `installer/AsterismLauncher.cs` by
`installer/build-stub.ps1`, using the C# compiler every Windows ships.)

**macOS / Linux:** `bash installer/install.sh`, then `asterism serve`
and open http://127.0.0.1:8642.

## Uninstall

Delete the Asterism folder (everything heavy — the math library, the
database, your problems and proofs — lives inside it) and the Desktop
shortcut. That's it.

The setup may also have installed shared developer tools — Python,
Git, the Lean toolchain (`%USERPROFILE%\.elan`), Claude Code — which
other software on your machine may now use; remove them the standard
way (Settings → Apps, or delete `.elan`) only if you're sure nothing
else needs them.

<details>
<summary>Manual install (developers)</summary>

```
pip install -e .
cd web && npm install && npm run build && cd ..
lake exe cache get        # Mathlib olean cache
asterism serve            # http://127.0.0.1:8642
```
</details>

## Web UI

One serve process per workspace. The whole lifecycle runs in the
browser: create a problem from a name and a natural-language
description (optionally grounded in shelf papers and engine
constraints), press Run on its page (the engine works one problem at
a time), and watch the sky: a live run strip names the phase and each
agent's unit, and the constellation draws the proof's true shape —
root-grown work above a horizon, other forward work beneath it with
citation threads crossing where it is used; while anything is live
the unproved stars carry the light. Machine settings live in the DB
behind the Manifest tab's controls (Manifest.md stays human prose,
hot-reloaded). The Papers page is the shelf: add PDFs by path, read
the original in place, bind citations. The Library page draws the
harvested corpus as one sky — searchable, and each star copies its
citation. The inbox collects everything that needs a human, with age
escalation on blocking requests. The engine page carries truthful
status (warm-up phase, last-exit verdict), model selects and knobs,
weighted-burn usage, and a developer-log fold. The UI is read-only
against the engine database; every action goes through the same
chokepoints as the CLI.

`cd web && npm run smoke` runs the Playwright smoke suite against a
live serve.

<!-- ASTERISM-PROGRESS:BEGIN -->
## Progress Log

### 2026-08-17
- Fixed bookkeeping bugs in how the system avoids duplicating work, including a truncated type-signature bug and a rule change so results claimed by one search branch remain reusable by others.
- Repaired a batch of edge-case bugs in proof verification and file editing, several of them exposed by an acceptance-testing pass.
- Let spawned worker agents write their output files directly to the server instead of through the sandbox, and updated their instructions to say exactly where outputs should go.

### 2026-08-16
- fix(spawn): never inherit stdin — a nested spawn was blocking on the MCP server's own pipe
- fix(recovery): bring pre-cascade trees under the law at startup
- fix(groups): a retired charter retires the work it delegated
- fix: four defects three independent verifiers found in today's fixes
- fix(context): say WHOSE dispatch state each panel describes
- fix(inspect): stop sending every reply twice, and name the deferred query in a form that can be resent
- fix(inspect): a bare filename resolves to THIS spawn's attempt, not whichever sorted first
- fix(strategist): a same-batch mark counts toward its Ingest — the exit catch-22 closes
- feat(delegate): the brief is a research proposal — and the experiment quota retires

### 2026-08-15
- Fixed several cost-accounting bugs so compute spending is now attributed to the right agent and the right call, including cases where a cancelled subprocess kept running or was wrongly charged.
- Made the shared progress report live-first, leading with current counts and a status breakdown of all lemmas before the full proof tree.
- Improved how agents read documents and receive feedback: large files can be read section by section, mistyped paths come back with a working correction, and all edit rejections are reported at once.
- Fixed reliability bugs in process handling and editor synchronization that could lose logs, stall proof checking, or make running work look lost.

### 2026-08-14
- Revised the instructions given to the AI agents in several places, resolving contradictory definitions, removing examples of an obsolete workflow, and adding explicit descriptions of failure patterns that superficially resemble progress.
- Made the system that farms work out to language-model backends more robust, so it now restarts bloated idle workers, recovers automatically when a backend dies, trusts the provider's own quota reports over local estimates, and checks capacity before launching new jobs.
- Added interface and installer options for choosing which AI model and account each worker uses, including support for a fourth account provider.
- Fixed several bugs in the tests and maintenance tooling, including tests that depended on the local machine, a cleanup audit that missed some leftover files, and a health check that misreported a probe that had never run as a failure.

### 2026-08-13
- Integrated a second language-model provider into the proving pipeline and fixed several faults uncovered during its first full run.
- Sharpened the adversarial verification rules so that a claimed record is only overturned by an actual proof, with separate checks for necessity and sufficiency.
- Repaired the resource-budgeting safeguards after three of them failed on the same afternoon, and made fallback accounting report itself explicitly.
- Cleaned up internal bookkeeping by deduplicating configuration tables, unifying job dispatch, and tightening tests around prompts and result inspection.

### 2026-08-12
- Fixed a batch of reliability problems in the service that coordinates automated proof attempts, including misattributed errors, mishandled worker sessions, and unresponsive workers now being followed up rather than written off.
- Repaired the sandboxed calculator, which had been rejecting valid mathematical expressions and hiding its own startup failures.
- Cleaned up record-keeping so each proof attempt is logged exactly once, failures are classified correctly, and completed steps report what they produced rather than only how they exited.
- Added a way to retract placeholder proofs flagged by pre-commit checks, moved public documentation to English, and fixed a continuous-integration configuration issue.

### 2026-08-11
- Improved the briefings handed to the automated prover agents, clarifying time limits, where searches may look, what a hand-off must include, and which tools are actually available to use.
- Held the agent that judges proof attempts to the same standards as the one that writes them, and gave reviews enough time that their supporting evidence is no longer cut short.
- Simplified the planning agent's decision loop, folding the step that declares a result ready into its main mathematical reasoning turn.
- Made project metadata get written once at creation so it cannot silently go stale, and let each group of problems carry its own conventions, inherited once from its parent.

### 2026-08-10
- Replaced the proving agents' general shell access with purpose-built tools — file inspection, content-anchored edits, and a network-isolated calculator — that give instructive feedback instead of raw errors.
- Tightened data boundaries, so each model provider now declares what it enforces and what it may read, with tests guarding the operator's own data as well as outside access.
- Made verification more honest, with proof-file checks now reporting whether a passing result covers the real build and machine crashes no longer counted as mathematical failures.
- Improved day-to-day operation with a clean shutdown command, clearer progress and blocker reporting in the web console, and an installer that adapts setup to the user's account and provider.

### 2026-08-07
- Rebuilt the web interface around the proof attempt itself: each branch is now labelled by the claim it was asked to prove, the search tree and its running log sit on one page, and settings moved to a page of their own.
- Added per-model usage accounting, so runs sharing a rate limit now pause together rather than one at a time.
- Began recording every change in a goal's status along with the event that caused it.
- Tightened what the language models are given and report back: evidence is no longer truncated mid-way, the lemma catalogue cites names that can actually be invoked, and edits report the exact line range they touched.

### 2026-08-06
- Broadened access to the literature: more open-access archives can now be fetched, the per-search result cap rose from 5 to 20, and papers can be pulled during a proof attempt rather than only in a separate setup step.
- The reviewing stage now reads fetched papers and completed proofs directly in place, retiring the size-capped staging copy that previously stood between them.
- Tightened acceptance: the reviewer can no longer pass its first criterion on an unsupported "looks fine", a run whose scope matches no known problem is refused outright, and a disproof mode used exactly once in the project's history was removed.
- Fixed bookkeeping bugs where a waiting sub-task let its parent proceed early, retrieved material was attached to the wrong revision of its goal, and two display glitches in the web view.

### 2026-08-04
- Fixed a task-queue bug in which an automatic retry after an infrastructure failure inserted a corrupted entry that silently stalled two provers, and added a recovery sweep to eliminate that whole class of failures.
- Made a failing prover's own last note part of the failure record that later attempts on the same problem get to see.
- Added safeguards against accumulated project notes degrading: warnings when shared documents grow too long, and deduplication of the lessons database.

### 2026-08-03
- Split the planning agent's periodic review into two passes — one for administrative housekeeping and one for actual mathematical reasoning — and made the administrative pass visible in the monitoring console.
- Paused a waiting goal's time budget while its subgoals are being worked on, so parent goals no longer expire during delegated work.
- Fixed the system to report library-search results accurately to the prover, and added recovery options for stalled proof attempts.
- Reorganized the prompt materials into a structured research-mission format with a shared conventions section, and let a finished subproblem's summary flow back to its parent on demand.

### 2026-08-02
- Designed and introduced a tree structure for organizing the collaborative discussion groups that work on a proof, then closed eleven gaps an independent review found and folded the design into the documentation.
- Extended the web interface so a proof attempt's argument can be read live while it is still running, following the new group structure.
- Fixed an assortment of smaller bugs in prompt wording, database schema, and run bookkeeping, including pinning each worker to the exact revision that authorized its goal.
- Repaired seven tests that had silently become unable to fail and added coverage for a tie-breaking edge case.

### 2026-08-01
- Fixed a bug where the root goal of a frozen proof attempt was not recognized as ready for dispatch, and made sure the adversarial reviewer now receives the full context document when judging results.
- Gave each spawned language-model agent its own restricted set of permissions, realized as an isolated per-agent environment.
- Updated the web interface so a running proof task displays its actual working text instead of a placeholder.
- Simplified the artifact-integrity audit by removing two redundant checksum layers while keeping the cross-check against the repository.

### 2026-07-31
- Reworked the example material in the agents' prompts so it teaches the general shape of a decision rather than reciting fixes for specific past problems.
- Fixed two validation bugs: restored a broken checker in the adversarial-critique step and made its critiques more complete, and closed a flaw where a JSON-format check could silently modify the data it inspected.
- Changed agents to invoke their tools directly instead of going through a shell, removing a fragile layer of indirection.

### 2026-07-30
- Added a soundness gate that blocks code-execution tricks in metaprogramming on every path a proof can be elaborated, closing a potential route to unsound proofs.
- Integrated a new subscription-based provider giving access to Google's Gemini models, and fixed credential handling that could silently fall back to the wrong account.
- Fixed several scheduling and reliability bugs, including agents being woken or reviewed prematurely and false alarms triggered by unrelated concurrent work.
- Removed dead code and obsolete internal terminology from an earlier design, and rewrote the architecture documentation to match the current system.

### 2026-07-29
- Fixed several bugs in the automated proof-review judge, including one that fed it degraded views of nested problems and a display bug that showed rejected proofs as passing.
- Rewrote and tightened the instructions guiding the proof-writing agents, adding explicit length limits on proof documents and clearer rules for when a one-line proof summary suffices.
- Reworked the rules for when agents may cite external lemmas, basing permission on the structure of the goal rather than a simple count, and removed outdated citation restrictions.
- Added a falsity check at problem intake so statements suspected to be unprovable are declined upfront.

### 2026-07-27
- Merged the three separate agents that translate informal mathematics into Lean into a single worker that proceeds through staged steps, and drafted a new set of prompts for it that is awaiting review before being switched on.
- Fixed a batch of bugs in that translation component, found through a systematic code review and a follow-up cleanup sweep, including a resource leak and stale-metadata issues.
- Corrected the verification safeguard so it checks that a theorem's statement is unchanged rather than comparing raw file contents, which had flagged harmless formatting edits.
- Updated the framework's configuration to a newer generation of language models, based on results from a hand-off experiment.

### 2026-07-26
- Reworked the automated critique step so proposed proofs are judged against each evaluation criterion separately, with the overall accept-or-reject decision now derived from those per-criterion verdicts.
- Shifted the proving pipeline to be natural-language-first: only fully argued informal proofs are handed off, and the proof-writing agents now formalize that argued proof into Lean rather than starting from scratch.
- Fixed a scheduling bug where internal timers were refreshed on every task instead of once per batch, eliminating a steady stream of unnecessary wake-ups.

### 2026-07-25
- Tightened the instructions given to the proving agents: proof-writing is now scoped to the current batch of steps, a step with unresolved gaps waits for a later batch, and several prompt files were corrected and trimmed.
- Required that informal natural-language proof sketches be argued to full logical closure, and made a mismatch between a formal step and its informal justification a documented failure mode that is escalated for review.
- Improved reliability by retrying transient network failures during rate-limit checks, and folded a separate periodic audit pass into the routine planning cycle.
- Updated the web dashboard to render agents' written reasoning as formatted prose with mathematical notation.

### 2026-07-24
- Tightened the reviewing agent's rules so a proof step can only be rejected with an explicit counter-argument, never demoted on a mere reservation.
- Clarified the division of labor for proof gaps: the proving agent must close its own gaps rather than hand them off, with formalization reserved for steps already settled.
- Landed a batch of small robustness fixes, including hard failures on bad configuration, earlier recovery from exhausted API quotas, and UTC-based log file naming.

### 2026-07-23
- Began shifting the system's internal proof drafts toward plain natural-language writing: the structured "thesis" summary was replaced by a prose proof section, and the accompanying briefs now explicitly flag gaps in the argument, using wording reviewed and approved by the maintainer.

### 2026-07-22
- Made uploading papers easier by replacing the manual file-path field with drag-and-drop in the browser.

### 2026-07-20
- Polished the web interface with a round of QA fixes, including chat improvements, keyboard-shortcut behavior, and having each chapter open to its corresponding theorem.
- Fixed an off-by-one line-counting error in the interactive synchronization.
- Reduced the worker pool from six to four to run one problem on its own and restore parity with the baseline setup.

### 2026-07-19
Programme revisions and worker declines now appear on the project's timeline and console, which previously left parts of the reasoning invisible.

- The adversary component was given read-only access to a problem's root definitions and shown their names, so its critiques can reference the actual objects in play.
- The web console gained the ability to resolve search patterns to concrete problems and survived crashes caused by cycles in the strategy hierarchy.
- The reset routine was hardened to sweep leftover plan and route files, so a fresh run no longer inherits stale state from a previous attempt.
- Memory accounting was corrected to stop double-counting a shared library cache, alongside a batch of smaller prompt and pipeline fixes.

<!-- ASTERISM-PROGRESS:END -->



