# localization_euclidean — BRIEF

_Auto-rendered from `Manifest.md` + `Library/`. The framework_
_inlines this file into `Context.md` for every Builder /_
_Backward dispatch on this problem._

## Sandbox
- Reads allowed without permission prompts:
  - This goal's problem dir (your cwd).
  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on Mathlib source.
- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant to this goal. Use Loogle / Grep on Mathlib instead.
- `Context.md` + `PAST_*.md` companion files: read-only.
- `patch.lean` is your single output. Lead with `--` annotation comments, then edit the body (Builder fills in the proof; Backward edits the strategy skeleton's body — signature locked). See the kind-specific prompt for layout.

## Strategic notes (from Manifest.md)
The classical construction has 3-4 layers:

1. **Define the localized valuation** `ν̃ : Localization S → ℕ` representative-
   independently. The simplest definition is `ν̃ ⟦(a, s)⟧ := EuclideanDomain.r a 0`-
   based — the "size of the numerator" — but this needs a representative
   choice. Use `Localization.liftOn` with a proof that the value doesn't
   depend on which `(a, s)` is picked.

2. **Define quotient and remainder** on `Localization S`. Given fractions
   `a/s` and `b/t` (both nonzero), pick a representative pair and reduce
   to `D`'s division. Concretely: `(a/s) = (b/t) · q + r` reduces to
   `at = bq's + r's·t` for some `q', r' ∈ D` after clearing denominators.

3. **Verify the Euclidean axioms** for the constructed `ν̃, quotient, remainder`:
   well-foundedness of `r`, the division identity, and `r remainder < r divisor`.

4. **Wrap into the instance**. The Mathlib `EuclideanDomain` structure
   bundles all the data; produce it via `EuclideanDomain.mk` or refine
   from the existing `CommRing (Localization S)` instance.

The key trick (from the user's HW): for `a/s ≠ 0`, the localized valuation
of `a/s` is `EuclideanDomain.r a 0` of the **numerator only** — denominators
are units in the localization. Independence-of-representative reduces to a
divisibility argument inside `D`. Don't expect a one-line proof; the
existence + axioms together will need 3-5 sub-goals.
