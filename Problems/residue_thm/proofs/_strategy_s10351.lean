import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_tau_dw_integrand_continuous_on_icc_prod

namespace Problems.residue_thm

-- Continuous function on the compact product `Icc 0 1 ×ˢ Icc 0 1` is bounded.
-- Sub-goal `tau_dw_integrand_continuous_on_icc_prod` packages the joint
-- continuity of the τ-derivative in (t, x); `IsCompact.exists_bound_of_continuousOn`
-- on `isCompact_Icc.prod isCompact_Icc` then yields the uniform bound, which is
-- repackaged as the double `∀ t ∀ x` conclusion via `Set.mk_mem_prod`.
theorem s10351
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∃ M : ℝ, ∀ t ∈ Set.Icc (0:ℝ) 1, ∀ x ∈ Set.Icc (0:ℝ) 1,
      ‖derivWithin (fun τ'' => f (H τ'' t) *
            derivWithin (H τ'') (Set.Icc (0:ℝ) 1) t)
        (Set.Icc (0:ℝ) 1) x‖ ≤ M  := by
  have h_cont :=
    tau_dw_integrand_continuous_on_icc_prod hV hf hH hHV hH0 hH1
  obtain ⟨M, hM⟩ :=
    (isCompact_Icc.prod isCompact_Icc).exists_bound_of_continuousOn h_cont
  refine ⟨M, fun t ht x hx => ?_⟩
  exact hM (t, x) (Set.mk_mem_prod ht hx)

end Problems.residue_thm
