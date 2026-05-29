import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct: `wlog i < j` (Disjoint is symmetric), set n = j - i ≥ 1, then
-- (g^j) '' D = (g^i) '' ((g^n) '' D) via pow_add + image_comp; cancel the injective g^i
-- (Set.disjoint_image_iff) to land on `(h n).symm : Disjoint D ((g^n) '' D)`.
theorem s11430 (g : E ≃ᵢ E) (D : Set E)
    (h : ∀ n : ℕ, 1 ≤ n → Disjoint ((g ^ n) '' D) D) :
    Pairwise (fun i j : ℕ => Disjoint ((g ^ i) '' D) ((g ^ j) '' D))  := by
  intro i j hij
  wlog hlt : i < j generalizing i j
  · have hji : j < i := (not_lt.mp hlt).lt_of_ne (Ne.symm hij)
    exact (this (Ne.symm hij) hji).symm
  set n := j - i with hn
  have hjn : j = i + n := by omega
  have h1n : 1 ≤ n := by omega
  have hcomp : (g ^ j) '' D = (g ^ i) '' ((g ^ n) '' D) := by
    rw [hjn, pow_add, ← Set.image_comp]
    rfl
  rw [hcomp, Set.disjoint_image_iff (g ^ i).injective]
  exact (h n h1n).symm

end Problems.Geometry.banach_tarski
