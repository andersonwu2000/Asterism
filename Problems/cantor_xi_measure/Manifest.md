---
problem: cantor_xi_measure
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# cantor_xi_measure — generalised Cantor set has Lebesgue measure 0

## Statement
∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
  MeasureTheory.volume (cantorSet ξ) = 0

## Lemma hints
- `MeasureTheory.volume` — Lebesgue measure on `ℝ` (`MeasureSpace.volume`)
- `MeasureTheory.measure_iInter_le` / `MeasureTheory.measure_le_of_subset` — bound a set's measure by any superset
- `Set.Icc 0 1` — the starting interval; `Real.volume_Icc` for its measure
- `Set.image_smul` / `MeasureTheory.Measure.measure_image` — measure under affine maps `x ↦ ax + b` rescales by `|a|`
- `MeasureTheory.Real.volume_image_mul_left` / `MeasureTheory.Measure.map_smul` — explicit scale formula
- `tendsto_pow_atTop_nhds_zero_of_lt_one` — `(1-ξ)^n → 0` when `0 ≤ 1-ξ < 1`
- `MeasureTheory.measure_iInter_eq_iInf` — measure of nested intersection (when one piece has finite measure)

## Strategic notes
Standard 4-step measure-theory argument:

1. **Each iterate has measure `(1−ξ)^n`.** Induct on `n`. Base: `volume (Icc 0 1) = 1`.
   Step: `cantorXi ξ (n+1)` is the disjoint union of two affine images of
   `cantorXi ξ n`, each scaled by `(1-ξ)/2`. So `volume (cantorXi ξ (n+1)) =
   2 · ((1-ξ)/2) · volume (cantorXi ξ n) = (1-ξ) · volume (cantorXi ξ n)`.
   The two images are disjoint because the right piece sits in `[(1+ξ)/2, 1]`
   and the left piece in `[0, (1-ξ)/2]`, separated by the gap `((1-ξ)/2, (1+ξ)/2)`.

2. **The Cantor set is contained in every iterate.** `cantorSet ξ ⊆ cantorXi ξ n`
   follows directly from the definition `cantorSet ξ = ⋂ n, cantorXi ξ n`.

3. **Measure inequality for all `n`.** From (1) and (2): `volume (cantorSet ξ)
   ≤ (1-ξ)^n` for every `n : ℕ`.

4. **Take the limit.** `0 < ξ < 1` gives `0 ≤ 1-ξ < 1`, so `(1-ξ)^n → 0`.
   A non-negative quantity bounded above by something tending to 0 is 0.

The disjointness in step 1 needs the `0 < ξ` hypothesis (otherwise the two
images overlap). The bound `1 - ξ < 1` is needed in step 4. Both endpoints
of the open interval `0 < ξ < 1` are essential.
