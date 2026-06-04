import Mathlib
namespace Problems.Minif2f.imo_1979_p1

-- tail_eq_pair_sum: split Icc 660 1319 into two image halves, pair up terms
-- Each j gives 1/(660+j) + 1/(1319-j) = 1979/((660+j)*(1319-j))
theorem tail_eq_pair_sum :
    (∑ k ∈ Finset.Icc (660 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))) =
      (1979 : ℝ) *
        ∑ j ∈ Finset.range 330,
          (1 : ℝ) / ((660 + (j : ℝ)) * (1319 - (j : ℝ))) := by
  have hset : Finset.Icc (660 : ℕ) 1319 =
      (Finset.range 330).image (· + 660) ∪ (Finset.range 330).image (fun j => 1319 - j) := by
    ext k; simp only [Finset.mem_Icc, Finset.mem_union, Finset.mem_image, Finset.mem_range]
    constructor
    · intro ⟨hk1, hk2⟩
      by_cases h : k ≤ 989
      · left; exact ⟨k - 660, by omega, by omega⟩
      · right; exact ⟨1319 - k, by omega, by omega⟩
    · intro h
      rcases h with ⟨j, hj, rfl⟩ | ⟨j, hj, rfl⟩ <;> omega
  have hdisj : Disjoint ((Finset.range 330).image (· + 660))
                         ((Finset.range 330).image (fun j => 1319 - j)) := by
    rw [Finset.disjoint_left]
    intro k hk1 hk2
    simp only [Finset.mem_image, Finset.mem_range] at hk1 hk2
    obtain ⟨j1, hj1, rfl⟩ := hk1
    obtain ⟨j2, hj2, h⟩ := hk2
    omega
  have hinj1 : ∀ j ∈ Finset.range 330, ∀ k ∈ Finset.range 330,
      j + 660 = k + 660 → j = k := by
    intros j _ k _ h; omega
  have hinj2 : ∀ j ∈ Finset.range 330, ∀ k ∈ Finset.range 330,
      1319 - j = 1319 - k → j = k := by
    intro j hj k hk h
    simp only [Finset.mem_range] at hj hk
    omega
  rw [hset, Finset.sum_union hdisj, Finset.sum_image hinj1, Finset.sum_image hinj2,
      ← Finset.sum_add_distrib, Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro j hj
  simp only [Finset.mem_range] at hj
  rw [show ((1319 - j : ℕ) : ℝ) = 1319 - (j : ℝ) from by
    rw [Nat.cast_sub (by omega)]; push_cast; ring]
  have h1 : (660 : ℝ) + (j : ℝ) ≠ 0 := by positivity
  have h2 : (1319 : ℝ) - (j : ℝ) ≠ 0 := by
    have : (j : ℝ) < 330 := by exact_mod_cast hj
    linarith
  push_cast
  field_simp [h1, h2]
  ring

end Problems.Minif2f.imo_1979_p1
