---
problem: localization_euclidean
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# localization_euclidean — `S⁻¹D` is Euclidean if `D` is

## Statement
∀ {D : Type*} [EuclideanDomain D] (S : Submonoid D),
  0 ∉ S → Nonempty (EuclideanDomain (Localization S))

## Entry kind
Backward
## Lemma hints
- `EuclideanDomain` — Mathlib structure with fields `r`, `quotient`, `remainder`, `quotient_mul_add_remainder_eq`, `r_wellFounded`, `remainder_lt`
- `Localization`, `Localization.mk`, `Localization.r` — the equivalence on `D × S` plus quotient construction
- `Localization.mk_eq_mk_iff` — when two fractions agree
- `Localization.lift` / `Localization.liftOn` — define functions out of the localization respecting the equivalence
- `EuclideanDomain.quotient`, `EuclideanDomain.remainder`, `EuclideanDomain.remainder_lt` — for transferring the underlying division
- `IsDomain` instance for `EuclideanDomain` (no zero divisors); `Localization.instIsDomain` if applicable

## Strategic notes
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
