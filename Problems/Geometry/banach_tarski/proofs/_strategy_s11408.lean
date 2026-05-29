import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_first_letter_residue_invariant
import Problems.Geometry.banach_tarski.proofs.L_map_prod_eq_pow_smul
import Problems.Geometry.banach_tarski.proofs.L_scaled_gen_eq_smul
import Problems.Geometry.banach_tarski.proofs.L_toword_ne_nil_of_ne_one

namespace Problems.Geometry.banach_tarski

-- Freeness middle-coordinate bound: cite the proved un-normalized residue invariant
-- (`swierczkowski_first_letter_residue_invariant`, s11396) for the integer triple
-- (p,q,r) with ¬3∣q realizing the product on ![0,1,0] = ![p√2, q, r√2], then transport
-- through the (1/3)-scaling. Three strictly-simpler sub-goals:
--   • `toword_ne_nil_of_ne_one` — w ≠ 1 ⇒ toWord w ≠ [] (gives the 1 ≤ length conjunct
--     and the s11396 nonemptiness premise); pure FreeGroup fact, no matrices.
--   • `map_prod_eq_pow_smul` — generic: a mapped list product of `c • g x` factors as
--     `c^len • (map g).prod`; pure list/smul induction, no matrices or √2.
--   • `scaled_gen_eq_smul` — per-letter: each scaled generator = (1/3) • its literal
--     un-normalized counterpart; a leaf casework discharged by the `hA..hBInv` defs.
-- Combine: hbridge rewrites the scaled product to `(1/3)^len • (unscaled prod)`,
-- `Matrix.smul_mulVec` pulls the scalar out, `hreal` evaluates the unscaled middle
-- coordinate to q, and the smul/coordinate simp lands `(1/3)^len * q`.
theorem s11408
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1 / 3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1 / 3 : ℝ) • !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hB : B = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hBInv : BInv = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    ∃ q : ℤ, ¬ (3 ∣ q) ∧ 1 ≤ (FreeGroup.toWord w).length ∧
      (Matrix.mulVec
        (((FreeGroup.toWord w).map
            (fun x : Fin 2 × Bool =>
              if x.1 = 0 then (if x.2 then A else AInv)
                         else (if x.2 then B else BInv))).prod)
        ![0, 1, 0]) 1
      = ((1 : ℝ) / 3) ^ (FreeGroup.toWord w).length * (q : ℝ)  := by
  have hne : (FreeGroup.toWord w) ≠ [] := toword_ne_nil_of_ne_one w hw
  obtain ⟨p, q, r, hq, _, hreal⟩ :=
    swierczkowski_first_letter_residue_invariant
      !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3]
      !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3]
      !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]
      !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]
      rfl rfl rfl rfl w hne
  have hbridge :
      (((FreeGroup.toWord w).map
          (fun x : Fin 2 × Bool =>
            if x.1 = 0 then (if x.2 then A else AInv)
                       else (if x.2 then B else BInv))).prod)
        = ((1 : ℝ) / 3) ^ (FreeGroup.toWord w).length •
          (((FreeGroup.toWord w).map
            (fun x : Fin 2 × Bool =>
              if x.1 = 0 then (if x.2 then !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3] else !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
                         else (if x.2 then !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1] else !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]))).prod) :=
    map_prod_eq_pow_smul ((1 : ℝ) / 3)
      (fun x : Fin 2 × Bool =>
        if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv))
      (fun x : Fin 2 × Bool =>
        if x.1 = 0 then (if x.2 then !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3] else !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
                   else (if x.2 then !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1] else !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]))
      (scaled_gen_eq_smul A AInv B BInv hA hAInv hB hBInv)
      (FreeGroup.toWord w)
  refine ⟨q, hq, List.length_pos_of_ne_nil hne, ?_⟩
  rw [hbridge, Matrix.smul_mulVec, hreal]
  simp [Pi.smul_apply, Matrix.cons_val_one, smul_eq_mul]

end Problems.Geometry.banach_tarski
