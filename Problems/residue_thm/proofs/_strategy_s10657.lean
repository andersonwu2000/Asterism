import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c1_path_concat_integral_sum_cont
import Problems.residue_thm.proofs.L_c1_path_reverse_integral_wrap

namespace Problems.residue_thm

-- Decompose into the dead-s10531 plan repaired with Q-continuity: build the C¹ loop
-- α · γ · β⁻¹ (closed since α 0 = β 0, α 1 = γ 0, β 1 = γ 1), apply h_loops, rearrange.
-- Sub-goal `c1_path_concat_integral_sum_cont` now takes `hQ_an` so its integral split
-- has IntervalIntegrable (the missing piece that made s10531's untyped concat unprovable
-- per its parent_needs_fix decline). `c1_path_reverse_integral_wrap` re-exposes the
-- already-proved `c1_path_reverse_integral` (Builder must inline since proved-sibling
-- citation is unavailable in patch.lean).
theorem s10657
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
      = (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t)  := by
  -- Construct the loop α · γ · β⁻¹ (closed since β 0 = α 0, β 1 = γ 1, α 1 = γ 0)
  -- as two C¹ concats plus a reverse; h_loops kills its integral.
  -- The Q-continuity hypothesis (from AnalyticOn → ContinuousOn) is what fixed the
  -- earlier dead s10531: the concat step's integral split requires IntervalIntegrable
  -- of Q∘path·deriv, which fails for arbitrary (non-measurable) Q.
  obtain ⟨β_rev, hβ_rev, hβ_rev0, hβ_rev1, hβ_rev_avoid, hβ_rev_int⟩ :=
    c1_path_reverse_integral_wrap (Q := Q) (a := a) hβ hβ_avoid
  obtain ⟨αγ, hαγ, hαγ0, hαγ1, hαγ_avoid, hαγ_int⟩ :=
    c1_path_concat_integral_sum_cont (Q := Q) (a := a) hQ_an hα hα_avoid hγ hγ_avoid hα1γ0
  have h_match : αγ 1 = β_rev 0 := by rw [hαγ1, hβ_rev0, hβ1γ1]
  obtain ⟨ψ, hψ, hψ0, hψ1, hψ_avoid, hψ_int⟩ :=
    c1_path_concat_integral_sum_cont (Q := Q) (a := a) hQ_an
      hαγ hαγ_avoid hβ_rev hβ_rev_avoid h_match
  have hψ_closed : ψ 0 = ψ 1 := by rw [hψ0, hψ1, hαγ0, hβ_rev1, hα0β0]
  have h_zero : (∫ t in (0:ℝ)..1, Q (ψ t) * deriv ψ t) = 0 :=
    h_loops ψ hψ hψ_avoid hψ_closed
  linear_combination hψ_int + hαγ_int + hβ_rev_int - h_zero

end Problems.residue_thm
