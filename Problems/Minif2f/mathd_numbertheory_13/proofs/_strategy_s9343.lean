import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs
import Problems.Minif2f.mathd_numbertheory_13.proofs.L_lt_89_implies_eq_39

namespace Problems.Minif2f.mathd_numbertheory_13

-- Decompose 89 ≤ v: any positive n with 14n%100=46 and n<89 must equal 39.
-- Since u = least element of S equals 39 (39 ∈ S and any element <89 equals 39),
-- and v ∈ S\{u} forces v ≠ u, suppose v<89 → v=39=u → contradiction.
theorem s9343 : ∀ (u v : ℕ) (S : Set ℕ) (_ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46) (_ : IsLeast S u) (_ : IsLeast (S \ {u}) v), 89 ≤ v  := by
  intro u v S hS hu hv
  by_contra h
  push_neg at h
  have h_lemma := lt_89_implies_eq_39
  have hvS : v ∈ S := hv.1.1
  have hvu : v ∉ ({u} : Set ℕ) := hv.1.2
  have hv_pos : 0 < v := ((hS v).mp hvS).1
  have hv_mod : 14 * v % 100 = 46 := ((hS v).mp hvS).2
  have hv_eq : v = 39 := h_lemma v hv_pos hv_mod h
  have h39_mem : (0 : ℕ) < 39 ∧ 14 * 39 % 100 = 46 := by decide
  have h39_in_S : 39 ∈ S := (hS 39).mpr h39_mem
  have hu_le_39 : u ≤ 39 := hu.2 h39_in_S
  have hu_pos : 0 < u := ((hS u).mp hu.1).1
  have hu_mod : 14 * u % 100 = 46 := ((hS u).mp hu.1).2
  have hu_lt_89 : u < 89 := by linarith
  have hu_eq : u = 39 := h_lemma u hu_pos hu_mod hu_lt_89
  apply hvu
  show v ∈ ({u} : Set ℕ)
  rw [Set.mem_singleton_iff, hv_eq, ← hu_eq]

end Problems.Minif2f.mathd_numbertheory_13
