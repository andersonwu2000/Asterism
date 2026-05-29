import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct (leaf) proof: finrank ℝ W ≤ 1 ⇒ via `finrank_le_one_iff` every x ∈ W is c • v
-- for a fixed v. A unit-norm c • v forces ‖c‖ * ‖v‖ = 1, i.e. c = ±‖v‖⁻¹, so the
-- sphere∩W set is contained in the 2-point set {‖v‖⁻¹ • v, -‖v‖⁻¹ • v}, hence finite.
theorem s11420
    (W : Submodule ℝ E) (hW : Module.finrank ℝ W ≤ 1) :
    {x ∈ Metric.sphere (0 : E) 1 | x ∈ W}.Finite  := by
  have h1 : ∃ v : E, ∀ x ∈ W, ∃ c : ℝ, x = c • v := by
    obtain ⟨v, hv⟩ := (finrank_le_one_iff (K := ℝ) (V := ↥W)).mp hW
    refine ⟨(v : E), fun x hx => ?_⟩
    obtain ⟨c, hc⟩ := hv ⟨x, hx⟩
    exact ⟨c, by simpa using congrArg (Subtype.val) hc.symm⟩
  obtain ⟨v, hv⟩ := h1
  apply Set.Finite.subset (s := {(‖v‖⁻¹ : ℝ) • v, (-(‖v‖⁻¹) : ℝ) • v})
  · exact (Set.finite_singleton _).insert _
  · intro x hx
    simp only [Set.mem_setOf_eq, Metric.mem_sphere, dist_eq_norm, sub_zero] at hx
    obtain ⟨hnorm, hxW⟩ := hx
    obtain ⟨c, rfl⟩ := hv x hxW
    rw [norm_smul, Real.norm_eq_abs] at hnorm
    have hc : |c| = ‖v‖⁻¹ := by
      rw [mul_comm] at hnorm; exact eq_inv_of_mul_eq_one_right hnorm
    rw [Set.mem_insert_iff, Set.mem_singleton_iff]
    rcases (abs_eq (by positivity)).mp hc with h | h
    · exact Or.inl (by rw [h])
    · exact Or.inr (by rw [h])

end Problems.Geometry.banach_tarski
