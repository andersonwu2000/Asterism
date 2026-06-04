import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct telescoping proof (no sub-goals): the gap term equals `B (t+1) - B t` for the
-- extended boundary `B i := if i < p then b ⟨i,_⟩ else n` (both branches of the dite collapse
-- to this since `t+1 ≥ p` forces `t+1 = p` and `B p = n`). Reindexing `Fin p → range p` and
-- applying `Finset.sum_range_tsub` (B is monotone from StrictMono/hlt) gives `B p - B 0 = n - B 0`;
-- `B 0 = 0` when `p>0` (hzero), and `n = 0` when `p = 0` (hp), closing both cases.
theorem s10937 {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    (∑ t : Fin p,
      (if h : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h⟩ - b t else n - b t)) = n  := by
  classical
  let B : ℕ → ℕ := fun i => if h : i < p then b ⟨i, h⟩ else n
  have hBp : B p = n := dif_neg (lt_irrefl p)
  have hBmono : Monotone B := by
    intro i j hij
    change (if h : i < p then b ⟨i, h⟩ else n) ≤ (if h : j < p then b ⟨j, h⟩ else n)
    by_cases hi : i < p
    · by_cases hj : j < p
      · rw [dif_pos hi, dif_pos hj]
        exact hmono.le_iff_le.2 (Fin.mk_le_mk.2 hij)
      · rw [dif_pos hi, dif_neg hj]
        exact (hlt ⟨i, hi⟩).le
    · rw [dif_neg hi]
      have hj : ¬ j < p := fun h => hi (lt_of_le_of_lt hij h)
      rw [dif_neg hj]
  have hterm : ∀ t : Fin p,
      (if h : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h⟩ - b t else n - b t)
        = B ((t : ℕ) + 1) - B (t : ℕ) := by
    intro t
    have hBt : B (t : ℕ) = b t := by
      change (if h : (t : ℕ) < p then b ⟨(t : ℕ), h⟩ else n) = b t
      rw [dif_pos t.isLt]
    by_cases h : (t : ℕ) + 1 < p
    · rw [dif_pos h, hBt]
      congr 1
      change b ⟨(t : ℕ) + 1, h⟩ = (if h' : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h'⟩ else n)
      rw [dif_pos h]
    · rw [dif_neg h, hBt]
      congr 1
      change n = (if h' : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h'⟩ else n)
      rw [dif_neg h]
  rw [Finset.sum_congr rfl (fun t _ => hterm t),
      Fin.sum_univ_eq_sum_range (fun i => B (i + 1) - B i) p,
      Finset.sum_range_tsub hBmono, hBp]
  rcases Nat.eq_zero_or_pos p with hp0 | hp0
  · have hn0 : n = 0 := by
      by_contra hn
      have := hp (Nat.pos_of_ne_zero hn); omega
    rw [hn0]; simp
  · have hB0 : B 0 = 0 := by
      change (if h : 0 < p then b ⟨0, h⟩ else n) = 0
      rw [dif_pos hp0]
      exact hzero ⟨0, hp0⟩ rfl
    rw [hB0, Nat.sub_zero]

end Problems.LinearAlgebra.jordan_normal_form
