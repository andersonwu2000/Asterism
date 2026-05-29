import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- cons_residue_arith: mod-3 residue invariant propagates through one-letter prepend
-- Case-splits on x and hclass; eliminates the inverse-head case via hhead; closes
-- non-divisibility by simp+omega on the four residue states; ModEq conclusions by simp.
theorem cons_residue_arith
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (x : Fin 2 × Bool) (M : List (Fin 2 × Bool))
    (hhead : M.head? ≠ some (x.1, !x.2))
    (p q r : ℤ) (hfold : List.foldr step (0, 1, 0) M = (p, q, r)) (hq : ¬ (3 ∣ q))
    (hclass :
      (M.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3])) :
    ∃ p' q' r' : ℤ,
      List.foldr step (0, 1, 0) (x :: M) = (p', q', r') ∧ ¬ (3 ∣ q') ∧
      ( ((x :: M).head? = some (0, true)  ∧ p' ≡ q'  [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        ((x :: M).head? = some (0, false) ∧ p' ≡ -q' [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        ((x :: M).head? = some (1, true)  ∧ q' ≡ -r' [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ∨
        ((x :: M).head? = some (1, false) ∧ q' ≡ r'  [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ) := by
  simp only [List.foldr, List.head?]
  rw [show List.foldr step (0, 1, 0) M = (p, q, r) from hfold]
  obtain ⟨ha, hb, hc, hd⟩ := hstep p q r
  fin_cases x <;> simp only [Fin.zero_eta, Fin.mk_one] at *
  · -- x = (0, true), step = (p-2q, 4p+q, 3r)
    rw [ha]
    refine ⟨p - 2*q, 4*p+q, 3*r, rfl, ?_, Or.inl ⟨trivial, ?_, ?_⟩⟩
    · rcases hclass with ⟨_, hpq, _⟩ | ⟨hM, _⟩ | ⟨_, _, hp⟩ | ⟨_, _, hp⟩
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hpq; omega
      · exact absurd hM hhead
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hp; omega
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hp; omega
    · simp [Int.ModEq]; omega
    · simp [Int.ModEq]
  · -- x = (0, false), step = (p+2q, -4p+q, 3r)
    rw [hb]
    refine ⟨p + 2*q, -4*p+q, 3*r, rfl, ?_, Or.inr (Or.inl ⟨trivial, ?_, ?_⟩)⟩
    · rcases hclass with ⟨hM, _⟩ | ⟨_, hpq, _⟩ | ⟨_, _, hp⟩ | ⟨_, _, hp⟩
      · exact absurd hM hhead
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hpq; omega
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hp; omega
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hp; omega
    · simp [Int.ModEq]; omega
    · simp [Int.ModEq]
  · -- x = (1, true), step = (3p, q-4r, 2q+r)
    rw [hc]
    refine ⟨3*p, q-4*r, 2*q+r, rfl, ?_, Or.inr (Or.inr (Or.inl ⟨trivial, ?_, ?_⟩))⟩
    · rcases hclass with ⟨_, _, hr⟩ | ⟨_, _, hr⟩ | ⟨_, hqr, hpz⟩ | ⟨hM, _⟩
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hr; omega
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hr; omega
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hqr hpz; omega
      · exact absurd hM hhead
    · simp [Int.ModEq]; omega
    · simp [Int.ModEq]
  · -- x = (1, false), step = (3p, q+4r, -2q+r)
    rw [hd]
    refine ⟨3*p, q+4*r, -2*q+r, rfl, ?_, Or.inr (Or.inr (Or.inr ⟨trivial, ?_, ?_⟩))⟩
    · rcases hclass with ⟨_, _, hr⟩ | ⟨_, _, hr⟩ | ⟨hM, _⟩ | ⟨_, hqr, hpz⟩
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hr; omega
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hr; omega
      · exact absurd hM hhead
      · intro ⟨k, hk⟩; apply hq; simp [Int.ModEq] at hqr hpz; omega
    · simp [Int.ModEq]; omega
    · simp [Int.ModEq]

end Problems.Geometry.banach_tarski
