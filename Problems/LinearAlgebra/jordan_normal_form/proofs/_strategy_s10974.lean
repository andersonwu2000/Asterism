import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_top_preimages_2
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_extended_jordan_family_strong
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_family_to_basis
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_ker_range_complement_2

namespace Problems.LinearAlgebra.jordan_normal_form

-- Assemble the strong block Jordan basis of `W` from the strong chain basis `d` of `range N`.
-- Discharge the two existential constructions via PROVED siblings, then run the LA glue:
--   * `block_top_preimages_2` (proved): lift each chain element through `N` → `x`, `hx`.
--   * `ker_range_complement_2` (proved): split `ker N` as `C ⊕ (range N ⊓ ker N)` → `C`, `hC*`.
--   * `extended_jordan_family_strong`: build the extended chain family `v` and prove
--     `LinearIndependent ∧ ⊤ ≤ span` (STRONG `hd` makes the dimension count close) + chain.
--   * `family_to_basis`: package an LI/spanning chain family into a `Module.Basis`,
--     transporting the chain property (generic, reusable; no `N`-structure reasoning).
-- The two preimage/complement siblings need only the WEAK `hd`, derived by dropping the
-- `j = 0` constraint from the strong left branch.
theorem s10974
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∃ (r : ℕ) (k : Fin r → ℕ)
      (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W),
      ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩  := by
  have hd_weak : ∀ (t : Fin p) (j : Fin (l t)),
      (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
        ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
          (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩ :=
    fun t j => (hd t j).imp (fun h => h.2) id
  obtain ⟨x, hx⟩ := block_top_preimages_2 N hN h_inv p l d hd_weak
  obtain ⟨C, hC1, hC2, hC3⟩ := ker_range_complement_2 N hN h_inv p l d hd_weak
  have hfam := extended_jordan_family_strong N hN h_inv p l d hd x hx C hC1 hC2 hC3
  exact family_to_basis N hfam

end Problems.LinearAlgebra.jordan_normal_form
