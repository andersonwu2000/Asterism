import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- image_from_witness: given a factorization witness (a,b,d) in the index ranges,
-- construct membership in the image finset via Finset.mem_image + Finset.mem_product.
theorem image_from_witness : ∀ n : ℕ, (∃ a b d : ℕ,
    (a ∈ Finset.Icc 3 8 ∧ b ∈ Finset.Icc 1 4 ∧ d ∈ Finset.Icc 0 1) ∧
    n = 2^a * 3^b * 5^3 * 7^d) →
    n ∈ ((Finset.Icc 3 8 ×ˢ Finset.Icc 1 4 ×ˢ Finset.Icc 0 1).image
      (fun p : ℕ × ℕ × ℕ => 2^p.1 * 3^p.2.1 * 5^3 * 7^p.2.2)) := by
  intro n ⟨a, b, d, ⟨ha, hb, hd⟩, hn⟩
  apply Finset.mem_image.mpr
  exact ⟨(a, b, d), Finset.mem_product.mpr ⟨ha, Finset.mem_product.mpr ⟨hb, hd⟩⟩, hn.symm⟩

end Problems.Minif2f.amc12a_2020_p21
