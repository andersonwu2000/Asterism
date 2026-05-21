import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10331

namespace Problems.residue_thm

-- homotopy_invariance_wrap: wrapper re-exporting s10331 (homotopy invariance of contour integral
-- under C² homotopy with fixed endpoints) so the framework auto-imports it via L_*.lean.
theorem homotopy_invariance_wrap
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V) (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    (∫ t in (0:ℝ)..1, f (H 0 t) * deriv (H 0) t) =
      (∫ t in (0:ℝ)..1, f (H 1 t) * deriv (H 1) t) := by
  exact s10331 hV hf hH hHV hH0 hH1

end Problems.residue_thm
