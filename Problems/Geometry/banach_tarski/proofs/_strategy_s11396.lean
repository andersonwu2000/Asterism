import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_matrix_prod_realizes_triple
import Problems.Geometry.banach_tarski.proofs.L_residue_invariant_foldr_list

namespace Problems.Geometry.banach_tarski

-- Reduce the Swierczkowski freeness invariant to pure-ℤ residue combinatorics
-- plus a matrix bridge. `step` is the concrete integer recursion (one branch per
-- generator letter), and `hstep` records its four defining equations.
--   • `residue_invariant_foldr_list` carries the inductive mod-3 residue invariant
--     on the reduced word list — no matrices, no √2, just integers (the real
--     induction, where ∃p q r,¬3∣q had to be strengthened to the head?-keyed
--     residue disjunction to become inductive).
--   • `matrix_prod_realizes_triple` transports the resulting integer triple back
--     through the generator matrices acting on ![0,1,0] (cites the proved
--     `matrix_prod_mulvec_realizes_foldr` + `rotation_generators_integer_recursion`).
-- The head?-residue disjunction is identical in parent and sub-goal A, so it
-- threads through unchanged.
theorem s11396
    (a aInv b bInv : Matrix (Fin 3) (Fin 3) ℝ)
    (ha : a = !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (haInv : aInv = !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hb : b = !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hbInv : bInv = !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (w : FreeGroup (Fin 2)) (hw : FreeGroup.toWord w ≠ []) :
    ∃ p q r : ℤ,
      ¬ (3 ∣ q) ∧
      ( ((FreeGroup.toWord w).head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ((FreeGroup.toWord w).head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ((FreeGroup.toWord w).head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        ((FreeGroup.toWord w).head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ) ∧
      Matrix.mulVec
        (((FreeGroup.toWord w).map
            (fun x : Fin 2 × Bool =>
              if x.1 = 0 then (if x.2 then a else aInv)
                         else (if x.2 then b else bInv))).prod)
        ![0, 1, 0]
      = ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2]  := by
  set step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ :=
    fun x t =>
      if x.1 = 0 then
        (if x.2 then (t.1 - 2 * t.2.1, 4 * t.1 + t.2.1, 3 * t.2.2)
                else (t.1 + 2 * t.2.1, -4 * t.1 + t.2.1, 3 * t.2.2))
      else
        (if x.2 then (3 * t.1, t.2.1 - 4 * t.2.2, 2 * t.2.1 + t.2.2)
                else (3 * t.1, t.2.1 + 4 * t.2.2, -2 * t.2.1 + t.2.2))
    with hstep_def
  have hstep : ∀ p q r : ℤ,
      step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
      step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
      step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
      step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r) := by
    intro p q r
    refine ⟨?_, ?_, ?_, ?_⟩ <;> simp [hstep_def]
  have hred : FreeGroup.reduce (FreeGroup.toWord w) = FreeGroup.toWord w :=
    FreeGroup.reduce_toWord w
  obtain ⟨p, q, r, hq, hdisj, hfold⟩ :=
    residue_invariant_foldr_list step hstep (FreeGroup.toWord w) hred hw
  exact ⟨p, q, r, hq, hdisj,
    matrix_prod_realizes_triple a aInv b bInv ha haInv hb hbInv step hstep w p q r hfold⟩

end Problems.Geometry.banach_tarski
