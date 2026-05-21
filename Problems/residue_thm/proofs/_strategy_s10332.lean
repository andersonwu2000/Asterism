import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_tau_partial_integrates_to_zero
import Problems.residue_thm.proofs.L_parametric_leibniz_homotopy_integral

namespace Problems.residue_thm

-- Interior parametric Leibniz + boundary vanishing.
-- (a) `parametric_leibniz_homotopy_integral` — at τ ∈ Ioo (0,1) the τ-derivative
--     of J τ := ∫ t, f(H τ t) * ∂_t H(τ,t) equals ∫ t, ∂_τ (f(H τ' t) * ∂_t H(τ',t)) τ
--     (Icc 0 1 ∈ 𝓝 τ unlocks Mathlib's parametric integral Leibniz; both factors are
--     C¹ in (τ,t) since `hf` is analytic and `hH` is ContDiffOn ℝ 2).
-- (b) `homotopy_tau_partial_integrates_to_zero` — the integral of the τ-partial is 0:
--     Cauchy–Riemann gives ∂_τ(f(H τ' t) * ∂_t H) = ∂_t(f(H τ' t) * ∂_τ H), then FTC
--     in t collapses to f(H τ 1)·∂_τ H(τ,1) − f(H τ 0)·∂_τ H(τ,0), which vanishes
--     because hH0/hH1 force H τ' 0 and H τ' 1 to be constant in τ'.
theorem s10332
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun τ => ∫ t in (0:ℝ)..1, f (H τ t) * deriv (H τ) t) 0 τ  := by
  intro τ hτ
  have h_leibniz :=
    parametric_leibniz_homotopy_integral hV hf hH hHV hH0 hH1 τ hτ
  have h_zero :=
    homotopy_tau_partial_integrates_to_zero hV hf hH hHV hH0 hH1 τ hτ
  rw [h_zero] at h_leibniz
  exact h_leibniz

end Problems.residue_thm
