import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- endo_finrank_one_eq_smul_id: finrank-1 endomorphism is scalar multiple of id
-- Uses finrank_eq_one_iff_of_nonzero to get a spanning vector v, extracts c from f v = c • v,
-- then shows f x = c • x for all x via scalar decomposition x = r • v.
-- entry_kind: Builder
theorem endo_finrank_one_eq_smul_id
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F = 1) :
    ∃ c : ℝ, f = c • LinearMap.id := by
  have hpos : 0 < Module.finrank ℝ F := hfin ▸ Nat.one_pos
  obtain ⟨v, hv0⟩ : ∃ v : F, v ≠ 0 := by
    have := Module.nontrivial_of_finrank_pos hpos; exact exists_ne 0
  have htop : ℝ ∙ v = ⊤ := (finrank_eq_one_iff_of_nonzero v hv0).mp hfin
  have hspan : ∀ w : F, ∃ c : ℝ, c • v = w := fun w => by
    have hmem : w ∈ (ℝ ∙ v) := htop ▸ Submodule.mem_top
    exact Submodule.mem_span_singleton.mp hmem
  obtain ⟨c, hc⟩ := hspan (f v)
  refine ⟨c, LinearMap.ext fun x => ?_⟩
  obtain ⟨r, hr⟩ := hspan x
  simp only [LinearMap.smul_apply, LinearMap.id_apply]
  rw [← hr, map_smul, ← hc, smul_smul, smul_smul, mul_comm]

end Problems.Geometry.banach_tarski
