---
problem: sylvester_gallai
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# sylvester_gallai — every non-collinear point set has an ordinary line

## Statement
∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q

## Entry kind
Backward
## Strategic notes

Sylvester–Gallai theorem. Freek-100; known proven, NOT in Mathlib.

The custom `Collinear p q r` is the determinant test
`(p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)` (see `Defs.lean`),
not Mathlib's `AffineSubspace`-based predicate.

Kelly's proof (1948):
- Consider pairs (line ℓ through ≥2 points of P, point p ∈ P off ℓ).
- Minimise the perpendicular distance from p to ℓ; pick minimiser (ℓ*, p*).
- Suppose ℓ* contains ≥3 points. The foot of perpendicular from p*
  has at least two of them on one side; the closer of those two with
  p* defines a line strictly closer to the third. Contradiction.
- Hence ℓ* has exactly 2 points of P.

## Lemma hints
- `Collinear p q r` ≝ `(p.1 - r.1)*(q.2 - r.2) = (p.2 - r.2)*(q.1 - r.1)`
- `Finset.min'_image` / `Finset.exists_min_image` — minimiser existence
- Real distance / arithmetic inequalities
- Classical `by_contra` + finite induction over `P.card`
