import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- cone_preserves_disjoint: disjoint cone lifts when sphere base sets are disjoint,
-- by recovering the unique unit direction via r = ‖y‖ (since ‖x‖=1, r>0)
theorem cone_preserves_disjoint (A B : Set E)
    (hA : A ⊆ Metric.sphere (0 : E) 1) (hB : B ⊆ Metric.sphere (0 : E) 1)
    (hdisj : Disjoint A B) :
    Disjoint {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A, y = r • x}
             {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ B, y = r • x} := by
  rw [Set.disjoint_left]
  intro y ⟨r₁, hr₁, x₁, hx₁A, hy₁⟩ ⟨r₂, hr₂, x₂, hx₂B, hy₂⟩
  have hx₁n : ‖x₁‖ = 1 := by
    have := hA hx₁A; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hx₂n : ‖x₂‖ = 1 := by
    have := hB hx₂B; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hr₁pos : (0 : ℝ) < r₁ := hr₁.1
  have hr₂pos : (0 : ℝ) < r₂ := hr₂.1
  have hr₁eq : ‖y‖ = r₁ := by
    rw [hy₁, norm_smul, Real.norm_of_nonneg hr₁pos.le, hx₁n, mul_one]
  have hr₂eq : ‖y‖ = r₂ := by
    rw [hy₂, norm_smul, Real.norm_of_nonneg hr₂pos.le, hx₂n, mul_one]
  have hrr : r₁ = r₂ := hr₁eq.symm.trans hr₂eq
  have hx_eq : x₁ = x₂ := by
    have h : r₁ • x₁ = r₁ • x₂ := hy₁.symm.trans (hrr ▸ hy₂)
    have := congr_arg (r₁⁻¹ • ·) h
    simp only [smul_smul, inv_mul_cancel₀ hr₁pos.ne', one_smul] at this
    exact this
  exact Set.disjoint_left.mp hdisj hx₁A (hx_eq ▸ hx₂B)

end Problems.Geometry.banach_tarski
