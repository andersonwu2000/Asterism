import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_residue_zero_decay_closed_loop_zero
import Problems.residue_thm.proofs.L_primitive_on_punctured_plane_from_zero_loops

namespace Problems.residue_thm

-- Split the primitive-existence into (1) closed-loop integrals vanish on ℂ\{a}
-- (uses analyticity + residue 0 + decay-at-∞, via Cauchy / principal-part / Liouville)
-- and (2) the abstract Morera-style construction of a primitive from the
-- closed-loop-zero hypothesis (uses path-independence of line integrals).
theorem s10485
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hQ_res : Complex.residue Q a = 0) :
    ∃ F : ℂ → ℂ, ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (Q z) z  := by
  have h_loops :
      ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
        (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
        (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0 := fun γ hγ h_avoid hclosed =>
    analytic_residue_zero_decay_closed_loop_zero hQ_an hQ_decay hQ_res γ hγ h_avoid hclosed
  exact primitive_on_punctured_plane_from_zero_loops hQ_an h_loops

end Problems.residue_thm
