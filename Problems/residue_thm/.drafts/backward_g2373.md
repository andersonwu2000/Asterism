### _progress.md

```
# Progress — hasderivat_from_segment_identity (salvaged from killed worker s10508)

The prior worker's patch.lean was complete (full proof body, not a
sketch) but the worker died before commit and its attempts_dir was
swept. The `new_<slug>.lean` stubs for the cited sub-goals
(`continuous_at_of_analytic_on_punctured`,
`hasderivat_from_segment_integral`) were lost — you must redeclare
them as new_<slug>.lean stubs when you commit your own strategy.
The framework will mint a fresh strategy id for your patch.lean —
rename `s10508` accordingly.

## Salvaged proposal comment

Pointwise dispatch: for each z ≠ a, combine continuity of Q at z
(from analyticity) with the segment-integral identity
F(z+h)-F z = ∫₀¹ Q(z+t·h)·h dt to conclude HasDerivAt F (Q z) z.
Sub-goals:
  (1) continuous_at_of_analytic_on_punctured — Builder:
      open-set analytic ⇒ ContinuousAt.
  (2) hasderivat_from_segment_integral — Backward: the analytic
      core (continuity at z + segment ID on Metric.ball z (dist z a)
      ⇒ HasDerivAt).

## Salvaged patch.lean body

```lean
theorem s<NEW_ID>
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    (F : ℂ → ℂ)
    (hF : ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t)
    (h_segment : ∀ z ∈ Set.univ \ ({a} : Set ℂ), ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), HasDerivAt F (Q z) z := by
  intro z hz
  have h_cont : ContinuousAt Q z :=
    continuous_at_of_analytic_on_punctured hQ_an z hz
  have h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h :=
    h_segment z hz
  exact hasderivat_from_segment_integral hz h_cont h_seg
```

## Sub-goal shapes to redeclare

- `continuous_at_of_analytic_on_punctured` — Builder leaf wrapper /
  short Backward: from `AnalyticOn ℂ Q (Set.univ \ {a})` and
  `z ∈ Set.univ \ {a}`, conclude `ContinuousAt Q z`. Direct via
  `AnalyticOn.continuousOn` + `IsOpen.mem_nhds`.
- `hasderivat_from_segment_integral` — Backward: from `ContinuousAt Q z`
  and the local segment-integral identity
  `∀ h, ‖h‖ < dist z a → F(z+h) - F z = ∫₀¹ Q(z + t·h) · h dt`,
  conclude `HasDerivAt F (Q z) z`. Core: extract little-o by
  uniform continuity of Q on a small ball around z.
```
