# Asterism

<!-- Add your project overview here. -->

<!-- ASTERISM-PROGRESS:BEGIN -->
## Progress Log

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

### 2026-06-18
- Reorganized the generated lemma library to group files by their dependency graph rather than by how problems were split, with sturdier retries and size limits that account for merged mutually-recursive groups.
- Switched proof generation and library cleanup to edit files incrementally through the Lean language server instead of regenerating them whole, behind a single shared routine.
- Made the cleanup and audit passes more reliable by rerunning fresh passes instead of retrying entire files and by confining their searches to the library directory.

### 2026-06-17
- Expanded the stage that tidies machine-proved lemmas into a clean, reusable library, enforcing Mathlib's submission standards: no compiler warnings, deduplicated variable blocks, consistent namespaces, and no unused hypotheses.
- Added whole-library consistency checks, including an editor-side validation that mirrors the checks run when results are committed.
- Carried out a broad documentation cleanup, fixing drift from the current code, garbled text, and scattered design notes, and added an automated guard to keep code-referencing docs in sync.

### 2026-06-16
- Tightened the integrity of generated proofs so an unfilled placeholder can no longer be cited as a proof of the main goal, and supporting definitions are now placed ahead of the results that rely on them.
- Made the automated search loop more robust against wasted effort, preventing duplicate attempts on the same goal, immediate retries of subgoals that had been set aside, and overly broad sweeps of stray files.
- Pruned the working proof tree down to its active frontier to keep the search focused.
- Improved observability by surfacing why a step stalls and keeping the run logs readable.

### 2026-06-15
- Improved reuse of equivalent subgoals, so an already-proved or in-progress goal is shared—or cited as a lemma—rather than re-derived.
- Hardened the subgoal scheduler to recover interrupted work after restarts and to avoid dropping or duplicating tasks.
- Refined the prompts and feedback given to the proving agents, giving clearer reasons when a step is declined and keeping self-reflection focused on the mathematics.

### 2026-06-14
- Overhauled the bookkeeping for concurrent proof attempts, adding an explicit "stalled" status to replace an earlier stopgap, keeping shelved attempts visible for review, and counting active searches by live processes rather than stale connections.
- Made each proving step elaborate exactly one unit against a single shared Lean compilation state.
- Refined the prover's instructions to look for an existing lemma before deriving a new intermediate step, and to back out of a subgoal only when its statement is genuinely malformed.

### 2026-06-13
- Unified how the system detects when a sub-problem has stalled, and extended automatic cleanup to cover sub-problems that had already collapsed into dead ends.
- A lemma that was shelved but never disproved is now revived whenever another step still cites it, with its statement reinserted so that step can be checked.
- Tightened how a goal is split into sub-goals: normalizing and de-duplicating their names, rejecting circular decompositions, and seeding each one with the right namespace context.

### 2026-06-12
- Built out a tower of definitions and 15 new problems leading up to Stokes' theorem, covering manifold boundaries and differential-form bundles.
- Improved how the system reuses existing library lemmas and definitions, fixing a series of edge cases around qualified names, local variable bindings, and citations.
- Made the prover more resilient to runaway or stalled Lean elaborations, cutting off stuck jobs instead of leaving them to hang.

### 2026-06-11
- Hardened the machinery that gathers generated definitions into a reusable Lean library, preserving docstrings, section variables, imports, and notation so relocated code still compiles.
- Improved how declarations are sorted into files, keeping each problem's definitions separate, redirecting shared ones, and capping how large any file can grow.
- Made concurrent file rewrites safe against race conditions and sharpened detection of stalled or timed-out proof-search attempts.
- Added framework support for theorems that discharge typeclass (instance) obligations.

### 2026-06-10
- Streamlined the pass that rewrites a finished proof into mathlib's idiom — aligning lemma names, trimming unused imports, and removing redundant references — folding many small steps into a few and fixing several cases where leftover references or errors were silently dropped.
- Made the task scheduler more robust to restarts and infrastructure failures, so stalled proof batches are retried rather than left stuck.
- Added packaging and continuous integration, and switched the proof-planning component to a newer model.

### 2026-06-09
- Refined the step that removes redundant lemmas and definitions from the generated proof library, including dropping thin wrappers that merely re-alias existing Mathlib results.
- Polished the cleaned-up Lean code by simplifying proofs, improving docstrings, removing unused arguments, and stripping internal framework comments and jargon.
- Reorganized declarations into sections with shared variables hoisted out, and ensured compiled files were rebuilt before verification checks were re-run.

### 2026-06-08
- Built a pipeline that scans its library of already-proven results and removes duplicate and definitionally-equal lemmas, processing declarations in dependency order with isolated type-checking.
- Fixed a parser that mishandled theorem statements whose conclusions carry quantifiers, and repaired a regression that had been crashing the deduplication pass.
- Sped that pass up sharply by reading the shared problem corpus only once, cutting one classification step from about 240 to 21 seconds.

### 2026-06-07
- Began deduplicating the automatically generated lemma library, dropping entries that merely re-prove results already in Mathlib.
- Added detection of trivial wrapper lemmas alongside an LLM-assisted pass for subtler duplicates, run per file in parallel with a separate verdict for each declaration.

### 2026-06-06
- Cleaned up duplicate entries in the shared library of proven results, adding a safeguard so that a result still relied on by another problem is never removed.

### 2026-06-05
- Proved three classical linear-algebra theorems — the Eckart–Young best low-rank approximation theorem, the Courant–Fischer min-max characterization of eigenvalues, and Sylvester's criterion — and added them to its reusable lemma library.
- A broader linear-algebra campaign produced several further new proofs and re-derived some earlier ones more compactly by reusing shared lemmas.
- The lemma library was turned into a cross-problem pool, so results established for one problem can now be reused as building blocks for others.
- Tightened the proof checker so that a verification timeout is reported as indeterminate rather than as a success.

### 2026-06-04
- Made the system's library of already-proved lemmas citable by new proof attempts, and trimmed that library down to only the lemmas the main theorem actually depends on, dropping unused leftovers.
- Hardened the machinery that renames and relocates those lemmas — redirecting stale references, reading proof files case-insensitively, ignoring `sorry` placeholders that appear only in comments, and checking a proof's axiom dependencies in a single pass.
- Backward search now discards subgoals that make no progress toward the goal, and a new check flags when a freshly introduced definition collides with an existing mathlib name so it can be renamed before proving continues.

### 2026-06-03
- Rebuilt how newly proved results get folded into the reusable library, replacing the language-model step with deterministic rules.
- Made that integration operate on one definition or lemma at a time, building and checking each incrementally instead of processing whole files at once.
- Fixed several reliability problems in the background library-maintenance process, including stuck sessions, leaked resources, and the handling of mutually-dependent files.
- Added a new soundness stress-test problem and improved the live monitoring of library work.

### 2026-06-02
- Made the component that reorganizes Asterism's accumulated library of lemmas raise an error instead of silently failing when asked to restructure a result it cannot handle.
- Improved its dependency tracking, correctly following dependencies through results that have been merged together and propagating requirements when a result rests on something not yet proven.
- Added automatic upgrading of an outdated but already-populated results database when it is opened.

### 2026-06-01
- Built out automatic integration of new results into the shared library, mechanically assembling migrated definitions and inserting `sorry` placeholders where proofs were not yet available.
- Fixed recurring migration failures by reconciling definition signatures, repairing the usage dependency graph, and redirecting references to definitions that had been merged together.
- Made the system recompile and re-verify the library files it edits, keeping per-step compiled artifacts current to avoid stale builds.
- Improved recovery from stalled work by re-queuing failed steps and re-opening an upstream result when a downstream change forced it to be reshaped.

### 2026-05-31
- Began building a system that automatically folds individually proven results into a shared, reusable library, de-duplicating and reclassifying each one as it is absorbed.
- Migrated the first result through this pipeline: a lemma characterizing Jordan normal form.
- Added safeguards to keep migrated results faithful, checking that each is definitionally equal to its original statement and free of unintended axioms.

### 2026-05-30
- Machine-checked a proof of the Banach–Tarski paradox for the closed unit ball in ℝ³.
- Added optional tooling to catalog the available library results and check their dependencies before use.

### 2026-05-29
- Forced UTF-8 console I/O so that proof goals containing mathematical Unicode symbols no longer crash the run on Windows.
- Hardened duplicate-goal detection to actually compile and check a candidate proof before accepting it, since the Lean build can report success while still emitting errors.
- Added safeguards so a goal that has already been proved can never be downgraded and set aside.
- Upgraded the underlying language models to the latest Opus release.

<!-- ASTERISM-PROGRESS:END -->



