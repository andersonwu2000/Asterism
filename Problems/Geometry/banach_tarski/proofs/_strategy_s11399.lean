import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_genmat_action_embed

namespace Problems.Geometry.banach_tarski

-- Split off the per-letter matrix action as the single sub-goal `genmat_action_embed`
-- (each generator matrix on an embedded triple `![p√2,q,r√2]` realizes one `step`
-- recursion — no word, no induction). The combinator is a plain list induction folding
-- that bridge over `toWord w` (inlined rather than citing the proved general lemma
-- `s11395`/`matrix_prod_mulvec_realizes_foldr`, whose module is not auto-imported into a
-- strategy file unless it is a registered sub-goal); `hfold` then rewrites foldr to (p,q,r).
theorem s11399
    (a aInv b bInv : Matrix (Fin 3) (Fin 3) ℝ)
    (ha : a = !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (haInv : aInv = !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hb : b = !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hbInv : bInv = !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (w : FreeGroup (Fin 2)) (p q r : ℤ)
    (hfold : List.foldr step (0, 1, 0) (FreeGroup.toWord w) = (p, q, r)) :
    Matrix.mulVec
        (((FreeGroup.toWord w).map
            (fun x : Fin 2 × Bool =>
              if x.1 = 0 then (if x.2 then a else aInv)
                         else (if x.2 then b else bInv))).prod)
        ![0, 1, 0]
      = ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2]  := by
  -- `hbridge` (sub-goal) gives the per-letter action; the rest is the list
  -- induction that folds it over the whole word (the structural combinator,
  -- inlined rather than citing the proved `s11395`, which is not auto-imported here).
  have hbridge := genmat_action_embed a aInv b bInv ha haInv hb hbInv step hstep

  set genMat : Fin 2 × Bool → Matrix (Fin 3) (Fin 3) ℝ :=
    fun x => if x.1 = 0 then (if x.2 then a else aInv) else (if x.2 then b else bInv) with hgen
  have general : ∀ (L : List (Fin 2 × Bool)) (v : ℤ × ℤ × ℤ),
      Matrix.mulVec ((L.map genMat).prod)
          ![(v.1 : ℝ) * Real.sqrt 2, (v.2.1 : ℝ), (v.2.2 : ℝ) * Real.sqrt 2]
        = ![((L.foldr step v).1 : ℝ) * Real.sqrt 2, ((L.foldr step v).2.1 : ℝ),
            ((L.foldr step v).2.2 : ℝ) * Real.sqrt 2] := by
    intro L
    induction L with
    | nil => intro v; simp
    | cons x xs ih =>
        intro v
        rw [List.map_cons, List.prod_cons, List.foldr_cons,
            ← Matrix.mulVec_mulVec, ih, hgen, hbridge]
  have key := general (FreeGroup.toWord w) (0, 1, 0)
  rw [hfold] at key
  simpa using key

end Problems.Geometry.banach_tarski
