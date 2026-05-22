import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- Direct construction by `Nat.rec` on a sigma-packaged `{U // T-invariant U}`:
-- the base picks `⊥` (vacuously invariant), and each successor uses `Classical.choose`
-- on the saturated extension hypothesis to produce the next invariant subspace; the four
-- conjuncts then unpack from the recursion definition and the choice spec.
theorem s10847 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = min (Module.finrank K U + 1) (Module.finrank K V)) →
      ∃ W : ℕ → Submodule K V,
        W 0 = ⊥ ∧
        (∀ i, W i ≤ W (i + 1)) ∧
        (∀ i, ∀ v ∈ W i, T v ∈ W i) ∧
        (∀ i, Module.finrank K (W (i + 1)) =
          min (Module.finrank K (W i) + 1) (Module.finrank K V))  := by
  intro K _ V _ _ _ T h_ext
  classical
  let WP : ℕ → {U : Submodule K V // ∀ v ∈ U, T v ∈ U} := fun n =>
    Nat.rec ⟨⊥, by intro v hv; rw [(Submodule.mem_bot K).1 hv]; simp⟩
            (fun _ p => ⟨Classical.choose (h_ext p.1 p.2),
                         (Classical.choose_spec (h_ext p.1 p.2)).2.1⟩) n
  refine ⟨fun i => (WP i).1, rfl, ?_, ?_, ?_⟩
  · intro i
    exact (Classical.choose_spec (h_ext (WP i).1 (WP i).2)).1
  · intro i; exact (WP i).2
  · intro i
    exact (Classical.choose_spec (h_ext (WP i).1 (WP i).2)).2.2

end Problems.LinearAlgebra.schur_triangularization
