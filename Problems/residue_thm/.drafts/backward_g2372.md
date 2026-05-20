### _progress.md

```
# Progress — path_diff_eq_connector (salvaged from killed worker s10506)

The prior worker's patch.lean was complete (full proof body, not a
sketch) but the worker died before commit and its attempts_dir was
swept. The `new_<slug>.lean` stubs for the cited sub-goals
(`c1_path_concat_integral_sum`, `c1_path_reverse_integral`) were
lost — you must redeclare them as new_<slug>.lean stubs when you
commit your own strategy. The framework will mint a fresh strategy
id for your patch.lean — rename `s10506` accordingly.

## Salvaged proposal comment

α · γ · β⁻¹ is a C¹ closed loop avoiding `a`; `h_loops` kills its
integral. Sub-goals provide the building blocks:
`c1_path_concat_integral_sum` smoothly glues two C¹ paths with
matching endpoint preserving the integral sum (used twice: α with
γ, then αγ with β⁻¹); `c1_path_reverse_integral` reverses β with
sign-flipped integral. Closing combinator: apply `h_loops` to ψ
and use `linear_combination` on the four integral equations.

## Salvaged patch.lean body

```lean
theorem s<NEW_ID>
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    {α β γ : ℝ → ℂ}
    (hα : ContDiffOn ℝ 1 α (Set.Icc 0 1))
    (hα_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, α t ≠ a)
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, β t ≠ a)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγ_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hα0β0 : α 0 = β 0)
    (hα1γ0 : α 1 = γ 0)
    (hβ1γ1 : β 1 = γ 1) :
    (∫ t in (0:ℝ)..1, Q (β t) * deriv β t) -
        (∫ t in (0:ℝ)..1, Q (α t) * deriv α t)
      = (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) := by
  have h_rev := c1_path_reverse_integral hQ_an h_loops hβ hβ_avoid
  have h_concat_ag :=
    c1_path_concat_integral_sum hQ_an h_loops hα hα_avoid hγ hγ_avoid hα1γ0
  obtain ⟨β_rev, hβ_rev, hβ_rev0, hβ_rev1, hβ_rev_avoid, hβ_rev_int⟩ := h_rev
  obtain ⟨αγ, hαγ, hαγ0, hαγ1, hαγ_avoid, hαγ_int⟩ := h_concat_ag
  have h_match : αγ 1 = β_rev 0 := by rw [hαγ1, hβ_rev0, hβ1γ1]
  have h_concat_full :=
    c1_path_concat_integral_sum hQ_an h_loops hαγ hαγ_avoid hβ_rev hβ_rev_avoid h_match
  obtain ⟨ψ, hψ, hψ0, hψ1, hψ_avoid, hψ_int⟩ := h_concat_full
  have hψ_closed : ψ 0 = ψ 1 := by rw [hψ0, hψ1, hαγ0, hβ_rev1, hα0β0]
  have h_zero : (∫ t in (0:ℝ)..1, Q (ψ t) * deriv ψ t) = 0 :=
    h_loops ψ hψ hψ_avoid hψ_closed
  linear_combination hψ_int + hαγ_int + hβ_rev_int - h_zero
```

## Sub-goal shapes to redeclare

- `c1_path_concat_integral_sum` — Backward: given two C¹ paths α, β
  with α 1 = β 0, produce a C¹ path αβ on Icc 0 1 with αβ 0 = α 0,
  αβ 1 = β 1, avoiding `a`, and ∫ Q∘αβ · αβ' = ∫ Q∘α · α' + ∫ Q∘β · β'.
- `c1_path_reverse_integral` — Backward: given C¹ β avoiding `a`,
  produce C¹ β_rev with β_rev 0 = β 1, β_rev 1 = β 0, avoiding `a`,
  and ∫ Q∘β_rev · β_rev' = -∫ Q∘β · β'.
```
