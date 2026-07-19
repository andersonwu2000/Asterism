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

### 2026-07-18
- Configuration changes can now be handed off to a run already in progress, and waiting for quota windows became an explicit opt-in rather than the default.
- The web interface gained an explainer chat that cites its claims back to the visualization, a unified prose renderer, and a set of layout and navigation fixes.
- Research mode gained a wider rebuttal budget, a longer hang guard, and a reworked external-review batch; the proof-search prompts were tightened around declined lemmas and goal-statement collisions.
- Several correctness fixes landed in the proof pipeline and its bookkeeping: chapter probes now carry module context, unconverged diagnostics no longer look clean, and telemetry and database cleanup were corrected.

### 2026-07-17
- Built out a new automated research pipeline that stores a working programme, gates each package, and runs multiple rounds of adversarial review with a path to discard weak candidates.
- Consolidated the web interface into a single engine view with unified tabbed pages, styling, and one Save button.
- Revised the guiding prompts through a self-review pass for consistency.

### 2026-07-16
- Capped the framework's library of general lessons at 25 entries, requiring an old one to be dropped whenever a new one is added.

### 2026-07-15
- Added an automated audit that flags when a prompt's stated routing no longer matches the project's central specification.
- Worked through two batches of user-reported issues, fixing problems in how the system spawns provers, assembles context, and drafts proof skeletons.

### 2026-07-14
- Trimmed the system's working memory to keep only recent context and deferred loading reference material until it is actually needed.
- Made the automated prover pause until its usage quota resets rather than shutting down when it hits the limit.
- Fixed cross-platform reliability problems on Windows and POSIX systems and applied self-audit corrections to earlier work.

### 2026-07-13
- Reworked the context given to the proving agents, adding an auto-generated index of already-proved results with full statements and replacing bulky search-tree dumps with compact on-demand summaries.
- Added a self-audit step that curates the accumulated knowledge base of proof lessons and prunes instructions made redundant by machine-generated context.
- Redesigned the web progress dashboard and fixed a dozen defects found in review, including cleaner grouping of goals and hiding of empty proof branches.
- Hardened sandboxing of spawned worker processes with a filesystem whitelist and fixed logging for background handoff tasks.

### 2026-07-12
- Gave each problem an explicit lifecycle state machine with checked transitions, so the system can only act on a problem when its state legally allows it.
- Hardened soundness guarantees: proofs are now pinned to a verified snapshot of the user's files, spawned provers cannot write outside their sandbox, and unauthorized axioms are stripped before a proof is accepted.
- Fixed several scheduling and bookkeeping bugs, including one where truncated error output made a failed proof attempt look like a success.
- Polished the web dashboard with layout fixes and a performance improvement when opening large problem sets.

### 2026-07-11
- Improved the web dashboard's proof-tree view with richer hover interactions — hovering a proof step now highlights its subgoals and their status — plus a redesigned legend and assorted polish from a usability audit.
- Added several safeguards against wasted work, so the system now declines to re-attempt a proof plan identical to one already tried and reuses results for goals whose statements are equivalent.
- Extended the pre-submission checks so more doomed proof steps are rejected by prediction before they are formally committed, including placeholder proofs and naming collisions.
- Upgraded the planning agent to periodically audit its own recorded beliefs rather than only the proof tree, to sign off on results with named evidence, and fixed a bug where its review loop mistook its own queued reminders for progress.

### 2026-07-10
- Registered the first batch of 50 Putnam competition problems from the PutnamBench benchmark, along with the plumbing to run them.
- Added offline, read-only telemetry to measure whether the system's accumulated proof knowledge actually pays off, and retired a citation-count metric that measured the wrong thing.
- Made long-running prover processes more robust: they now survive the process that launched them, hand off cleanly when the code changes underneath them, and stale servers can no longer go undetected.
- Improved the monitoring interface to show proofs as they are being drafted, fixed display glitches, and tightened tracking of exactly which lemmas each Lean proof depends on.

### 2026-07-09
Out-of-budget open goals now route to human review instead of looping fruitlessly, and parked work no longer masquerades as active proving.

- The one-click Windows installer was consolidated into a single `Asterism.exe` with a web-based first-run setup, plus a more resilient Python bootstrap that self-heals broken 3.12 installs, accepts any Python ≥3.12, and runs Lean and Mathlib setup on parallel tracks.
- The web interface gained a unified camera engine shared across the proof-search and library views, directional citation arcs, automatic layout-cleanup passes, richer run cards showing the full proof body, and problem deletion behind a confirmation guard.

### 2026-07-08
- Rebuilt the one-click installer and setup wizard to run unattended with live progress, a reliable minimal Python and pinned Lean toolchain, and browser-based login.
- Added the ability to settle a requested claim as false by proving its negation, while keeping such a disproof clearly distinct from an ordinary success.
- Made the proof-graph viewer show each goal's real Lean source and proof, and overhauled its layout to minimize edge crossings and center the diagram cleanly.
- Wired the "harvest to Library" action to launch its run immediately.

### 2026-07-07
- Added the ability for readers to run Lean code directly in the browser, including a live display of the proof goal at the cursor while editing.
- Built agent-driven fetching of cited papers from academic databases (arXiv, OpenAlex, Crossref), with an in-app shelf for viewing the PDFs alongside problems.
- Moved harvesting of proved definitions into the shared library behind an explicit human sign-off step, and reworked the library so it reads like a textbook.
- Shipped a Windows installer with a browser-based setup wizard, and overhauled the run-monitoring console and proof-graph visualizations for readability and performance.

### 2026-07-06
- Built a browser interface for the framework, with a dashboard of running problems, an interactive proof-tree view for each one, a queue for decisions needing human review, and a control panel for the background proving process.
- Refined the interface's visual design through dozens of iteration passes, including an external design audit, a full color-palette overhaul, and accessibility and layout fixes.
- Added a pipeline for ingesting research papers and tracing proof claims back to their sources, exercised on two new test problems about traces of SL(2,ℤ) monodromy matrices.
- Fixed assorted backend issues, including a race condition that could bypass a final sign-off check, and added per-run token accounting to the database.

### 2026-07-05
- Extended the automated prover so its forward-exploration stage can now invent new inductive types, structures, and named instances rather than only lemmas, with database and validation support exercised on fresh toy problems.
- Added a Hilbert-style propositional calculus benchmark whose target is the deduction theorem, alongside other small test problems.
- Fixed several reliability bugs, including a Windows command-line length limit that silently killed large prompts and a background process that refused to shut down after fatal errors.
- Strengthened the infrastructure with a CI tier that runs against a real Lean toolchain, a versioned record of already-proved problems for regression checking, and a lemma library index consolidated into the database.

### 2026-07-04
- Replaced fragile text-pattern extraction of Lean declarations with direct queries to the Lean compiler and language server, so theorem names and definitions are now read from ground truth.
- Centralized the check that marks a theorem as proved at a single chokepoint and closed a gap where declarations containing incomplete proofs could slip past validation.
- Reworked task scheduling so each problem is tracked through to one well-defined terminal state, with the database schema and tests updated to match.
- Hardened the infrastructure with startup checks of the framework's assumptions about Lean's interface, a crash-consistency audit, unified configuration handling, and refactored scheduling, retry, and proof-assembly plumbing.

### 2026-07-03
- Extended the axiom-soundness check to run at more decision points, including after every rewrite that follows a library merge, so no proof is accepted that silently depends on extra axioms.
- Funneled all remaining proof and status writes through single checked entry points, adding a lint rule to keep unaudited writes from creeping back in.
- Fixed several bugs in merging finished proofs into the shared library, including mishandled universe declarations, false duplicate detection, and aliases that lost modifiers or could not be cited.
- Rewrote the architecture documentation to match actual system behavior and tightened rules around how pipelines claim and use work slots.

### 2026-07-02
- Added a check that reads directly from the Lean kernel to record exactly which axioms and assumptions each proved result relies on.
- Built a workflow to designate the intended theorems and then accept them behind a required human sign-off, or reject them so that everything built on a discarded result is automatically invalidated.
- Fixed the archiving step to store only the approved theorems rather than everything reachable from the starting goal.

### 2026-06-30
- Fixed the component that catalogs Lean definitions so it now strips comments before reading declaration names, preventing commented-out code from being mistaken for real definitions.

### 2026-06-29
- Added an automatic lemma pre-search that, for each step of a proof attempt, looks for useful lemmas first in the problem itself, then a local library, then Mathlib, capping results per source and using a configurable time budget, in place of the old hand-written hints.
- Fixed two verification flaws so a proof is only accepted after re-checking it against the current compiler diagnostics and on its own workspace, rather than trusting stale or borrowed results.
- Kept the background worker alive until its finished proofs are collected, so completed work is no longer lost.

### 2026-06-28
- Improved the generation of Lean proof files so that declaration modifiers like `noncomputable` are preserved and the necessary definition imports are pulled in.
- Consolidated the system's accumulated "lessons" into a single global store, retiring the older per-step lessons and an obsolete seed file.
- Hardened proof storage so every saved proof passes an ownership check and writes no longer leave stray backup files behind.
- Tightened reliability with assorted fixes: crashes now log a full traceback before shutdown, resetting a problem cleans up its dependent records, and the test suite was made cleaner and more portable.

### 2026-06-27
- Built a mechanism for the prover to learn from its own failures, recording which approaches did not work, storing them in a searchable lessons file, and surfacing only those relevant to the goal currently being proved.
- Enabled proofs to automatically reuse already-proved results from the same problem when they are cited, while blocking citations that reach into unrelated problems.
- Fixed a crash when recording lessons for problems with qualified names and stripped leftover internal annotations from saved proof files.

### 2026-06-26
- Added a knowledge base that records lessons and recurring failure patterns from past proof attempts, and started feeding them into the context assembled for new proofs.
- Fixed the guidance for searching previously proved related results so it matches the actual proof files.

### 2026-06-23
- Enabled the system to retract or correct its own earlier guidance once a proof attempt shows that guidance to be false.
- Gave the proving agent more local context, surfacing relevant definitions' signatures, clashing names, and the lines around its most recent edit.

### 2026-06-22
- Tightened internal bookkeeping so the database and on-disk proof files can no longer drift apart, routing every proof-file change through a single consistency checkpoint and all proof-state changes through one guarded gateway.
- Improved handling of incomplete proofs, letting the prover read the goal at an unsolved `sorry`, carry variable declarations into generated proof skeletons, and validate its own output.
- Made the system more resilient by recovering the minimal set of library imports when import-trimming times out and by reliably cleaning up spawned helper processes.

### 2026-06-21
- Improved how newly proved results are filed into the reusable library, computing each result's precise dependencies and ordering them consistently.
- Dropped the catch-all Mathlib import when existing library files already supplied what a result needed, and kept definitions' original namespaces intact during the move.
- Reorganized the archiving code into a cleaner structure and removed dead code.

### 2026-06-20
- Added automated tidying of code style — normalizing whitespace and blank lines — in the generated proof library, with fixes so that recompiling a file never left its compiled output missing or stale.
- Strengthened the safety checks that move lemmas between files so they now reject any change that would create a circular dependency among imports.
- Fixed the per-declaration compilation checks to faithfully reproduce each file's namespace (`open`) context, and protected core definitions from being modified during cleanup.

### 2026-06-19
- Expanded the automated cleanup of finished proofs, adding a pass that renames unused hypotheses with a leading underscore and moving the validation checks into an already-loaded Lean environment for speed, though the type-checking check was rolled back after it caused repeated spurious rework.
- Added a way to categorize the feedback returned during proof attempts alongside a separate diagnostic channel, and fixed a model reasoning-budget setting that had fallen below the API's minimum.

<!-- ASTERISM-PROGRESS:END -->



