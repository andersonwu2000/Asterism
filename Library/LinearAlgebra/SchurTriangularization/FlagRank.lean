import Mathlib

namespace Library.LinearAlgebra.SchurTriangularization.FlagRank

-- Direct construction by `Nat.rec` on a sigma-packaged `{U // T-invariant U}`:
-- the base picks `⊥` (vacuously invariant), and each successor uses `Classical.choose`
-- on the saturated extension hypothesis to produce the next invariant subspace; the four
-- conjuncts then unpack from the recursion definition and the choice spec.
theorem extension_iteration_sequence :
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

-- rank_chain_min_eq: pure ℕ-induction converting step-rank equation to closed form
theorem rank_chain_min_eq :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = min (Module.finrank K U + 1) (Module.finrank K V)) →
      ∀ (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, Module.finrank K (W (i + 1)) =
        min (Module.finrank K (W i) + 1) (Module.finrank K V)) →
      ∀ i, Module.finrank K (W i) = min i (Module.finrank K V) := by
  intro K _ V _ _ _ T _hext W hW0 hWstep i
  induction i with
  | zero =>
    simp [hW0]
  | succ n ih =>
    rw [hWstep, ih]
    omega

-- saturated_one_step_extension: wraps one-step extension hypothesis to saturate at finrank V
theorem saturated_one_step_extension :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        Module.finrank K U < Module.finrank K V →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = Module.finrank K U + 1) →
      ∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = min (Module.finrank K U + 1) (Module.finrank K V) := by
  intro K _ V _ _ _ T h_ext U hU
  by_cases h : Module.finrank K U < Module.finrank K V
  · obtain ⟨U', hle, hinv, hrank⟩ := h_ext U hU h
    exact ⟨U', hle, hinv, by rw [hrank, Nat.min_eq_left h]⟩
  · have h' : Module.finrank K V ≤ Module.finrank K U := Nat.le_of_not_lt h
    have heq : Module.finrank K U = Module.finrank K V :=
      Nat.le_antisymm (Submodule.finrank_le U) h'
    exact ⟨U, le_refl _, hU, by rw [heq, min_eq_right (Nat.le_succ _)]⟩

-- Two-step packaging: (1) `extension_iteration_sequence` constructs the recursive
-- flag W : ℕ → Submodule K V from the saturated one-step extension hypothesis,
-- giving W 0 = ⊥, the chain, T-invariance at every level, and the *step* rank
-- equation `finrank (W (i+1)) = min (finrank (W i) + 1) (finrank V)`.
-- (2) `rank_chain_min_eq` is a pure ℕ-induction lemma converting that step rank
-- equation, together with W 0 = ⊥, into the closed-form `finrank (W i) = min i (finrank V)`.
theorem iterate_extension_to_flag :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = min (Module.finrank K U + 1) (Module.finrank K V)) →
      ∃ W : ℕ → Submodule K V,
        W 0 = ⊥ ∧
        (∀ i, W i ≤ W (i + 1)) ∧
        (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) ∧
        (∀ i, ∀ v ∈ W i, T v ∈ W i)  := by
  intro K _ V _ _ _ T h_ext
  have h_seq := extension_iteration_sequence T h_ext
  have h_rank := rank_chain_min_eq T h_ext
  obtain ⟨W, hW0, hW_le, hW_inv, hW_step⟩ := h_seq
  exact ⟨W, hW0, hW_le, h_rank W hW0 hW_step, hW_inv⟩

end Library.LinearAlgebra.SchurTriangularization.FlagRank
