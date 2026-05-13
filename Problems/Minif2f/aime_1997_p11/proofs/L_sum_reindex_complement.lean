import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- sum_reindex_complement: Finset.sum_nbij with involution n ↦ 45-n on Icc 1 44
-- rewrites the LHS sum over (45-n)π/180 to the RHS sum over nπ/180;
-- term equality uses Nat.cast_sub to equate (45:ℝ)-↑n with ↑(45-n).
set_option linter.style.longLine false in
theorem sum_reindex_complement :
    (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (((45 : ℝ) - n) * π / 180)) =
    (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin ((n : ℝ) * π / 180)) := by
  apply Finset.sum_nbij (fun n => 45 - n)
  · intro n hn
    simp only [Finset.mem_Icc] at hn ⊢
    omega
  · intro a ha b hb hab
    rw [Finset.mem_coe, Finset.mem_Icc] at ha hb
    simp only at hab
    omega
  · intro b hb
    rw [Finset.mem_coe, Finset.mem_Icc] at hb
    simp only [Set.mem_image, Finset.mem_coe, Finset.mem_Icc]
    exact ⟨45 - b, ⟨by omega, by omega⟩, by omega⟩
  · intro n hn
    simp only [Finset.mem_Icc] at hn
    have hle : n ≤ 45 := by omega
    congr 1
    rw [Nat.cast_sub hle]
    push_cast
    ring

end Problems.Minif2f.aime_1997_p11
