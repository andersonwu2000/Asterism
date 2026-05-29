import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_length_pow_inv_of
import Problems.Geometry.banach_tarski.proofs.L_wrd_of_tower_image

namespace Problems.Geometry.banach_tarski

-- Orbit tower D, ρ^i''D (ρ = φ(of 1)⁻¹), is pairwise disjoint because the
-- address `wrd` of any element of ρ^i''D equals (of 1)⁻¹^i (hcoh: wrd(φ w•x)=w*wrd x,
-- with wrd x=1 on D since head?=none), and the reduced word (of 1)⁻¹^i has length i —
-- a strictly-increasing invariant, so i≠j ⇒ disjoint.
-- Sub-goals: `wrd_of_tower_image` (address of a tower element) and
-- `length_pow_inv_of` (length of the pure FreeGroup power). Combiner: a shared y
-- forces (of 1)⁻¹^i = (of 1)⁻¹^j, take toWord-length to get i = j ⊥ hij.
theorem s11490
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    Pairwise (fun i j : ℕ => Disjoint
        (((φ (FreeGroup.of 1))⁻¹ ^ i) ''
          {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none})
        (((φ (FreeGroup.of 1))⁻¹ ^ j) ''
          {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}))  := by
  intro i j hij
  rw [Set.disjoint_left]
  rintro y hyi hyj
  apply hij
  have key : ((FreeGroup.of (1:Fin 2))⁻¹) ^ i = ((FreeGroup.of (1:Fin 2))⁻¹) ^ j :=
    (wrd_of_tower_image φ M rep wrd hcoh i y hyi).symm.trans
      (wrd_of_tower_image φ M rep wrd hcoh j y hyj)
  have hcong := congrArg (fun w => (FreeGroup.toWord w).length) key
  simpa [length_pow_inv_of] using hcong

end Problems.Geometry.banach_tarski
