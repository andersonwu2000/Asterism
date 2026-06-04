import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- gap_terms_prefix: telescoping sum of consecutive gaps b(j+1)-b(j) over Fin t equals b t;
-- induction on k, dif_pos holds since j<k<p implies j+1<p, nat subtraction closed by omega
-- entry_kind: Builder
theorem gap_terms_prefix {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∀ t : Fin p,
      (∑ j : Fin ↑t,
        (fun (s : Fin p) =>
          if h : (s : ℕ) + 1 < p then b ⟨(s : ℕ) + 1, h⟩ - b s else n - b s)
            (Fin.castLE t.isLt.le j)) = b t := by
  have key : ∀ (k : ℕ) (hk : k < p),
      (∑ j : Fin k,
        (fun (s : Fin p) =>
          if h : (s : ℕ) + 1 < p then b ⟨(s : ℕ) + 1, h⟩ - b s else n - b s)
            (Fin.castLE hk.le j)) = b ⟨k, hk⟩ := by
    intro k
    induction k with
    | zero =>
      intro hk
      simp only [Fin.sum_univ_zero]
      exact (hzero ⟨0, hk⟩ rfl).symm
    | succ k ih =>
      intro hk
      have hk' : k < p := Nat.lt_of_succ_lt hk
      rw [Fin.sum_univ_castSucc]
      have step1 : ∀ j : Fin k,
          (fun (s : Fin p) =>
            if h : (s : ℕ) + 1 < p then b ⟨(s : ℕ) + 1, h⟩ - b s else n - b s)
              (Fin.castLE hk.le (Fin.castSucc j)) =
          (fun (s : Fin p) =>
            if h : (s : ℕ) + 1 < p then b ⟨(s : ℕ) + 1, h⟩ - b s else n - b s)
              (Fin.castLE hk'.le j) := by
        intro j; congr 1
      rw [Finset.sum_congr rfl (fun j _ => step1 j)]
      rw [ih hk']
      have hlast : Fin.castLE hk.le (Fin.last k) = ⟨k, hk'⟩ := by
        ext; simp [Fin.castLE, Fin.last]
      rw [hlast]
      dsimp only
      have hkp : k + 1 < p := hk
      rw [dif_pos hkp]
      have hmono_le : b ⟨k, hk'⟩ ≤ b ⟨k + 1, hk⟩ := Nat.le_of_lt (hmono (by simp))
      omega
  intro t
  exact key t.val t.isLt

end Problems.LinearAlgebra.jordan_normal_form
