import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- Direct proof: even numbers in [1,1319] = image of (·*2) on [1,659], then sum_image.
theorem s9726 :
    (∑ k ∈ (Finset.Icc (1 : ℕ) 1319).filter (fun k => Even k),
        ((1 : ℝ) / (k : ℝ))) =
      (∑ j ∈ Finset.Icc (1 : ℕ) 659, ((1 : ℝ) / ((2 * j : ℕ) : ℝ)))  := by
  have hset : (Finset.Icc (1 : ℕ) 1319).filter (fun k => Even k)
              = (Finset.Icc (1 : ℕ) 659).image (fun j => 2 * j) := by
    ext k
    simp only [Finset.mem_filter, Finset.mem_Icc, Finset.mem_image]
    constructor
    · rintro ⟨⟨h1, h2⟩, hev⟩
      obtain ⟨r, hr⟩ := hev
      refine ⟨r, ⟨?_, ?_⟩, ?_⟩ <;> omega
    · rintro ⟨j, ⟨hj1, hj2⟩, rfl⟩
      refine ⟨⟨?_, ?_⟩, ?_⟩
      · omega
      · omega
      · exact ⟨j, by omega⟩
  rw [hset, Finset.sum_image (fun j _ k _ h => by simp at h; omega)]
end Problems.Minif2f.imo_1979_p1
