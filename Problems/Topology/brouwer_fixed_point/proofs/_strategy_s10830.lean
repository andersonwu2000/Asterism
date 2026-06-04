import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- Direct conjugation transfer of a fixed point across `φ : S ≃ₜ T`.
-- Set `h := φ ∘ g ∘ φ.symm : T → T`; continuity is `fun_prop` from `hg`,
-- `φ.continuous`, `φ.symm.continuous`. Brouwer on T gives `y` with `h y = y`;
-- applying `φ.symm` to both sides yields `g (φ.symm y) = φ.symm y`.
theorem s10830
    {α β : Type*} [TopologicalSpace α] [TopologicalSpace β]
    {S : Set α} {T : Set β}
    (φ : S ≃ₜ T)
    (g : S → S) (hg : Continuous g)
    (hbrouwer : ∀ (h : T → T), Continuous h → ∃ y, h y = y) :
    ∃ x : S, g x = x  := by
  have hcont : Continuous (fun y : T => φ (g (φ.symm y))) := by fun_prop
  obtain ⟨y, hy⟩ := hbrouwer _ hcont
  refine ⟨φ.symm y, ?_⟩
  have h := congrArg φ.symm hy
  simp only [Homeomorph.symm_apply_apply] at h
  exact h

end Problems.Topology.brouwer_fixed_point