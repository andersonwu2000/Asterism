import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_primitive_punctured_of_decay_residue_zero
import Problems.residue_thm.proofs.L_subtracted_analytic_off_singularity
import Problems.residue_thm.proofs.L_subtracted_residue_zero
import Problems.residue_thm.proofs.L_subtracted_tendsto_zero_cocompact

namespace Problems.residue_thm

-- Decompose into (i) algebraic facts about Q := P - r/(·-a) (analyticity, decay,
-- residue 0) and (ii) the structural punctured-plane primitive lemma. Sub-goal (4)
-- carries the analytic content (Cauchy / principal-part / monodromy); (1)–(3) are
-- bookkeeping that combine cleanly via the abstract primitive lemma.
theorem s10480
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    ∃ F : ℂ → ℂ, ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (P z - Complex.residue P a / (z - a)) z  := by
  set r : ℂ := Complex.residue P a with hr_def
  set Q : ℂ → ℂ := fun z => P z - r / (z - a) with hQdef
  have hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}) :=
    subtracted_analytic_off_singularity (P := P) (a := a) hP
  have hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0) :=
    subtracted_tendsto_zero_cocompact (P := P) (a := a) hP_tendsto
  have hQ_res : Complex.residue Q a = 0 :=
    subtracted_residue_zero (P := P) (a := a) hP
  obtain ⟨F, hF⟩ :=
    primitive_punctured_of_decay_residue_zero (Q := Q) (a := a) hQ_an hQ_decay hQ_res
  refine ⟨F, ?_⟩
  intro z hz
  simpa [hQdef, hr_def] using hF z hz

end Problems.residue_thm
