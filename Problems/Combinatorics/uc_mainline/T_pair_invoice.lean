import Mathlib
import Problems.Combinatorics.uc_mainline.Defs
import Problems.Combinatorics.uc_mainline.T_projection_accounts
import Problems.Combinatorics.uc_mainline.T_witness_number_deficit

/-!
# Theorem P1 of `uc_minimal_deficit_pair.md` (the pair invoice)

> **Theorem P1 (the pair invoice).** For every `j in V'`,
>
>     G_2 is capped at j   <=>   sigma_j(I_x) + sigma_j(I'_k) <= sigma_j(F)
>                          <=>   D(x -> j) + sigma_j(I'_k) <= 0,
>
> where `D(x -> j) = sigma_j(I_x) - sigma_j(F)` is the single-projection
> witness number of Theorem A.

(`uc_minimal_deficit_pair.md`, Section 5b.3; `V' = V ∖ {x, k}`,
`G_2 = pairProj F x k`, `I_x = edgeTrace F x`, `I'_k = edgeTrace (proj F x) k`,
`D(x → j) = witnessD F x j`.)
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

variable {V : Type*} [DecidableEq V] [Fintype V]

-- As in `T_projection_accounts.lean`, nothing here needs `[Fintype V]`; the instance is kept
-- in the signatures so that the whole main line shares one context.
set_option linter.unusedSectionVars false

/-! ## The pair projection is the projection of the projection -/

/-- `π_{x,k}(F) = π_k(π_x(F))`: removing `{x, k}` is removing `x` and then `k`. -/
theorem pairProj_eq_proj_proj (F : Finset (Finset V)) (x k : V) :
    pairProj F x k = proj (proj F x) k := by
  ext c
  simp only [pairProj, proj, Finset.mem_image]
  constructor
  · rintro ⟨S, hS, rfl⟩
    exact ⟨S.erase x, ⟨S, hS, rfl⟩, (sdiff_pair_eq_erase_erase S x k).symm⟩
  · rintro ⟨d, ⟨S, hS, rfl⟩, rfl⟩
    exact ⟨S, hS, sdiff_pair_eq_erase_erase S x k⟩

/-- Lemma 5b.3.1 in deficit form: the two invoices of the iterated projection add up,
`σ_j(G_2) + σ_j(I_x) + σ_j(I'_k) = σ_j(F)` for `j ∈ V'`. -/
theorem pairProj_sigma_add (F : Finset (Finset V)) (x k j : V) (hjx : j ≠ x) (hjk : j ≠ k) :
    sigma (pairProj F x k) j + sigma (edgeTrace F x) j
      + sigma (edgeTrace (proj F x) k) j = sigma F j := by
  have h1 := proj_sigma_add (proj F x) k j hjk
  have h2 := proj_sigma_add F x j hjx
  rw [pairProj_eq_proj_proj]
  omega

/-! ## Theorem P1 -/

/-- Theorem P1, first equivalence: `G_2` is capped at `j ∈ V'` iff
`σ_j(I_x) + σ_j(I'_k) ≤ σ_j(F)`. -/
theorem pairProj_capped_at_iff (F : Finset (Finset V)) (x k j : V) (hxk : x ≠ k)
    (hjx : j ≠ x) (hjk : j ≠ k) :
    0 ≤ sigma (pairProj F x k) j ↔
      sigma (edgeTrace F x) j + sigma (edgeTrace (proj F x) k) j ≤ sigma F j := by
  have h := pairProj_sigma_add F x k j hjx hjk
  omega

/-- Theorem P1, second equivalence: `G_2` is capped at `j ∈ V'` iff
`D(x → j) + σ_j(I'_k) ≤ 0`. -/
theorem pairProj_capped_at_iff_witnessD (F : Finset (Finset V)) (x k j : V) (hxk : x ≠ k)
    (hjx : j ≠ x) (hjk : j ≠ k) :
    0 ≤ sigma (pairProj F x k) j ↔
      witnessD F x j + sigma (edgeTrace (proj F x) k) j ≤ 0 := by
  have h := pairProj_sigma_add F x k j hjx hjk
  have hw := witnessD_eq_sigma_sub F x j hjx
  omega

#print axioms pairProj_capped_at_iff
#print axioms pairProj_capped_at_iff_witnessD

end Problems.Combinatorics.uc_mainline
