import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_shift_image
import Problems.Geometry.banach_tarski.proofs.L_tail_eq

namespace Problems.Geometry.banach_tarski

-- ρ''T = T∖D for the hotel T = ⋃ₙ ρⁿ''D: push ρ through the union (shift), then
-- peel the n=0 term using pairwise-disjoint orbits.
-- h_shift: image of union + ρ∘ρⁿ = ρⁿ⁺¹ collapses ρ''T to the shifted union ⋃ₙ ρⁿ⁺¹''D
--   (pure set algebra, no disjointness).
-- h_tail: the shifted union is exactly T with the n=0 piece D removed; ⊇ is trivial,
--   ⊆ uses hdisj (every ρⁿ⁺¹''D is disjoint from ρ⁰''D = D). Combine by rewriting.
theorem s11476 (D : Set E) (ρ : E ≃ᵢ E)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    ρ '' (⋃ n : ℕ, (ρ ^ n) '' D) = (⋃ n : ℕ, (ρ ^ n) '' D) \ D  := by
  have h_shift := shift_image D ρ
  have h_tail := tail_eq D ρ hdisj
  rw [h_shift, h_tail]

end Problems.Geometry.banach_tarski
