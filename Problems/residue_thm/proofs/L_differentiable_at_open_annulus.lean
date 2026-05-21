import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- differentiable_at_open_annulus: restricts AnalyticOn to DifferentiableAt on open annulus
-- via differentiableOn on the open punctured ball, then neighbourhood argument.
theorem differentiable_at_open_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r₁ r₂ : ℝ} (hr₁ : 0 < r₁) (hle : r₁ ≤ r₂) (hr₂ : r₂ < R) :
    ∀ z ∈ Metric.ball z₀ r₂ \ Metric.closedBall z₀ r₁, DifferentiableAt ℂ f z := by
  intro z hz
  have hzR : z ∈ Metric.ball z₀ R := Metric.ball_subset_ball hr₂.le hz.1
  have hzne : z ∉ ({z₀} : Set ℂ) := by
    simp only [Set.mem_singleton_iff]
    intro h
    exact hz.2 (h ▸ Metric.mem_closedBall_self hr₁.le)
  have hmem : z ∈ Metric.ball z₀ R \ {z₀} := ⟨hzR, hzne⟩
  have hopen : IsOpen (Metric.ball z₀ R \ {z₀}) :=
    IsOpen.sdiff Metric.isOpen_ball isClosed_singleton
  exact hf.differentiableOn.differentiableAt (hopen.mem_nhds hmem)

end Problems.residue_thm
