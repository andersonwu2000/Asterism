---
problem: NumberTheory.cube_e2e
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# NumberTheory.cube_e2e — anchor+claim flow e2e (Forward-defined def used in a delivered claim)

## Statement
True

## Strategic notes

This problem exercises the **anchor+claim** collaboration flow, NOT hard math.
The root `main : True` is **vestigial scaffolding** — prove it trivially
(`trivial`) whenever; it carries no content.

The real product is two **Forward-generated deliverables** to harvest into the
Library:

1. **A definition.** `Inject(Forward)` a `def isPerfectCube (n : ℕ) : Prop := ∃ k, n = k ^ 3`.
   (It is a `def`, not a theorem — it ships proved immediately.)
2. **A claim that USES that definition.** `Inject(Forward)` a
   `theorem eight_is_cube : isPerfectCube 8`. Its statement must reference the
   `isPerfectCube` def from step 1, so the Forward file must
   `import Problems.NumberTheory.cube_e2e.proofs.L_isPerfectCube` and cite
   `isPerfectCube` by name. Prove it with the witness `k = 2` (`⟨2, by norm_num⟩`).

Order matters: land the definition FIRST (step 1), then the claim (step 2),
because step 2's statement depends on step 1's def existing.

Once **both** have landed, `MarkDeliverable` each of them. Then `Ingest`.

Produce and mark the deliverables BEFORE reopening/proving the trivial root, so
the ingest sign-off governs the harvest (not the root-proved auto-trigger).
