import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- single_letter_residue_base: base case of mod-3 residue invariant for single-letter words [x],
-- computed directly from hstep applied to (0,1,0) for each of the 4 generators.
theorem single_letter_residue_base
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (x : Fin 2 × Bool) :
    ∃ p q r : ℤ,
      List.foldr step (0, 1, 0) [x] = (p, q, r) ∧ ¬ (3 ∣ q) ∧
      ( ([x].head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ([x].head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ([x].head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        ([x].head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ) := by
  fin_cases x <;> simp only [List.foldr, List.head?]
  · -- x = (0, true): step (0,true) (0,1,0) = (-2, 1, 0)
    refine ⟨-2, 1, 0, ?_, ?_, Or.inl ⟨rfl, ?_, ?_⟩⟩
    · have h := (hstep 0 1 0).1; norm_num at h; exact h
    · norm_num
    · norm_num [Int.ModEq]
    · norm_num [Int.ModEq]
  · -- x = (0, false): step (0,false) (0,1,0) = (2, 1, 0)
    refine ⟨2, 1, 0, ?_, ?_, Or.inr (Or.inl ⟨rfl, ?_, ?_⟩)⟩
    · have h := (hstep 0 1 0).2.1; norm_num at h; exact h
    · norm_num
    · norm_num [Int.ModEq]
    · norm_num [Int.ModEq]
  · -- x = (1, true): step (1,true) (0,1,0) = (0, 1, 2)
    refine ⟨0, 1, 2, ?_, ?_, Or.inr (Or.inr (Or.inl ⟨rfl, ?_, ?_⟩))⟩
    · have h := (hstep 0 1 0).2.2.1; norm_num at h; exact h
    · norm_num
    · norm_num [Int.ModEq]
    · norm_num [Int.ModEq]
  · -- x = (1, false): step (1,false) (0,1,0) = (0, 1, -2)
    refine ⟨0, 1, -2, ?_, ?_, Or.inr (Or.inr (Or.inr ⟨rfl, ?_, ?_⟩))⟩
    · have h := (hstep 0 1 0).2.2.2; norm_num at h; exact h
    · norm_num
    · norm_num [Int.ModEq]
    · norm_num [Int.ModEq]
end Problems.Geometry.banach_tarski
