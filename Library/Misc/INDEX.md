# Library/Misc — INDEX

- `compactness` — ∀ {α : Type} (S : Set (PropForm α)), (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S

- `gen_generates` — ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n), x ∈ Subgroup.zpowers (gen n)

- `proj_nonexpansive` — ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X] {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty → ∀ {P : X → X}, IsMetricProjector K P → ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖

- `inner_zero_iff_smul` — ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X] (x y : X), inner ℝ x y = 0 ↔ ∀ α : ℝ, ‖x + α • y‖ = ‖x - α • y‖

- `cantor_xi_measure` — ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → MeasureTheory.volume (cantorSet ξ) = 0
