import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- f_h_continuous_on_icc: ContinuousOn (f ∘ H τ) on Icc 0 1 via composition of
-- analytic f (hence continuous on V) with the C² slice H τ (hence continuous on Icc 0 1).
theorem f_h_continuous_on_icc
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      ContinuousOn (fun t => f (H τ t)) (Set.Icc (0:ℝ) 1) := by
  intro τ hτ
  have hτ' : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have hHcont : ContinuousOn (fun t => H τ t) (Set.Icc (0:ℝ) 1) := by
    have hcomp : ContinuousOn (fun t : ℝ => (τ, t)) (Set.Icc (0:ℝ) 1) :=
      by fun_prop
    have hmaps : Set.MapsTo (fun t : ℝ => (τ, t)) (Set.Icc (0:ℝ) 1)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
      fun t ht => ⟨hτ', ht⟩
    exact hH.continuousOn.comp hcomp hmaps
  exact hf.continuousOn.comp hHcont (fun t ht => hHV τ hτ' t ht)

end Problems.residue_thm
