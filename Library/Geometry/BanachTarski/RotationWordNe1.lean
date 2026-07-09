import Library.Geometry.BanachTarski.SwierczkowskiResidues

/-!
# Nontriviality of rotation words in SO(3)

This module establishes that a reduced word in the free group on two generators, mapped to a
specific pair of rotation matrices in $\mathrm{SO}(3)$ (scaled by $1/3$), evaluates to a
nontrivial matrix. Together with
`SwierczkowskiResidues.swierczkowski_first_letter_residue_invariant`, this implies that the
lift of the two generators to $\mathrm{SO}(3)$ is injective.

## Main statements

- `rotation_word_ne_one_of_reduced`: a nontrivial reduced word maps to a matrix ≠ 1.
- `freegroup_lift_injective_of_word_prod_ne_one`: injectivity of `FreeGroup.lift f` from
  a word-product non-triviality condition.

## Implementation notes

Each generator is `(1/3) • M` for an integer-entry matrix `M`. The word product equals
`(1/3)^n • U` where `n = (toWord w).length ≥ 1`. The residue invariant gives integers `p q r`
with `¬ 3 ∣ q` satisfying `U.mulVec ![0, 1, 0] = ![p√2, q, r√2]`. If the product were the
identity, the middle coordinate forces `(1/3)^n * q = 1`, hence `q = 3^n` — divisible by 3
for `n ≥ 1` — a contradiction.
-/

open Library.Geometry.BanachTarski.SwierczkowskiResidues

namespace Library.Geometry.BanachTarski.RotationWordNe1

/-- If each of `A`, `AInv`, `B`, `BInv` equals `(1/3) • M` for the respective integer-entry
matrices `MA`, `MAInv`, `MB`, `MBInv`, then the product of a list of these matrices equals
`(1/3)^n • U`, where `n` is the list length and `U` is the product of the unscaled matrices. -/
theorem scaled_word_prod
    (A AInv B BInv MA MAInv MB MBInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1 / 3 : ℝ) • MA) (hAInv : AInv = (1 / 3 : ℝ) • MAInv)
    (hB : B = (1 / 3 : ℝ) • MB) (hBInv : BInv = (1 / 3 : ℝ) • MBInv)
    (l : List (Fin 2 × Bool)) :
    (l.map (fun x : Fin 2 × Bool =>
        if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv))).prod
    = (1/3 : ℝ) ^ l.length •
      (l.map (fun x : Fin 2 × Bool =>
        if x.1 = 0 then (if x.2 then MA else MAInv) else (if x.2 then MB else MBInv))).prod := by
  subst hA hAInv hB hBInv
  induction l with
  | nil => simp
  | cons x xs ih =>
    rw [List.map_cons, List.prod_cons, List.map_cons, List.prod_cons, ih,
      List.length_cons, pow_succ', ← smul_ite, ← smul_ite, ← smul_ite,
      smul_mul_assoc, mul_smul_comm, smul_smul]

-- `simp only` lemmas for evaluating Fin-indexed vector components at index 1 require `simp?`
set_option linter.flexible false in
/-- Given `U.mulVec ![0, 1, 0] = ![p√2, q, r√2]` and `(c • U).mulVec ![0, 1, 0] = ![0, 1, 0]`,
the middle coordinate forces `c * q = 1`. -/
theorem smul_mulvec_middle (c : ℝ) (p q r : ℤ) (U : Matrix (Fin 3) (Fin 3) ℝ)
    (hU : U.mulVec ![0, 1, 0] = ![(p : ℝ) * Real.sqrt 2, (q : ℝ), (r : ℝ) * Real.sqrt 2])
    (h1 : (c • U).mulVec ![0, 1, 0] = ![0, 1, 0]) :
    c * (q : ℝ) = 1 := by
  have hsmul : c • U.mulVec ![0, 1, 0] = ![0, 1, 0] := by
    rw [← Matrix.smul_mulVec]; exact h1
  rw [hU] at hsmul
  have h2 := congr_fun hsmul 1
  simp [smul_eq_mul] at h2
  exact h2

/-- If `(1/3)^n * q = 1` with `n > 0`, then `3 ∣ q`. Indeed `q = 3^n`, which is divisible
by 3 for positive `n`. -/
theorem three_dvd_of_pow_inv_mul (n : ℕ) (q : ℤ) (_hn : 0 < n)
    (h : (1 / 3 : ℝ) ^ n * (q : ℝ) = 1) : (3 : ℤ) ∣ q := by
  have hq : (q : ℝ) = (3 : ℝ) ^ n := by
    have key : (3 : ℝ) ^ n * ((1 / 3 : ℝ) ^ n * (q : ℝ)) = (3 : ℝ) ^ n := by
      rw [h]; ring
    rw [← mul_assoc, ← mul_pow] at key
    norm_num at key
    linarith
  have hq_int : q = (3 : ℤ) ^ n := by exact_mod_cast hq
  rw [hq_int]
  exact dvd_pow_self 3 (by omega)

/-- **Rotation word nontriviality**: the product of a reduced word `w ≠ 1` in the specific
generators `A`, `AInv`, `B`, `BInv` (the $1/3$-scaled rotation matrices) is not the identity.

Each generator is `(1/3) • M` for an integer-entry matrix `M`, so the word product equals
`(1/3)^n • U` where `n = (toWord w).length ≥ 1` and `U` is the unscaled product. The residue
invariant `swierczkowski_first_letter_residue_invariant` gives integers `p q r` with `¬ 3 ∣ q`
and `U.mulVec ![0, 1, 0] = ![p√2, q, r√2]`. If the product were the identity, the middle
coordinate would force `(1/3)^n * q = 1`, hence `q = 3^n` — divisible by 3 for `n ≥ 1` —
contradicting `¬ 3 ∣ q`. -/
theorem rotation_word_ne_one_of_reduced
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1 / 3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1 / 3 : ℝ) • !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hB : B = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hBInv : BInv = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    ((FreeGroup.toWord w).map
        (fun x : Fin 2 × Bool =>
          if x.1 = 0 then (if x.2 then A else AInv)
                     else (if x.2 then B else BInv))).prod
      ≠ (1 : Matrix (Fin 3) (Fin 3) ℝ) := by
  intro hP
  have hne : FreeGroup.toWord w ≠ [] := fun h => hw (FreeGroup.toWord_eq_nil_iff.mp h)
  set U : Matrix (Fin 3) (Fin 3) ℝ :=
    ((FreeGroup.toWord w).map
        (fun x : Fin 2 × Bool =>
          if x.1 = 0 then (if x.2 then !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3]
                                  else !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
                     else (if x.2 then !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]
                                  else !![3, 0, 0; 0, 1, 2 * Real.sqrt 2;
                                      0, -2 * Real.sqrt 2, 1]))).prod
    with hU_def
  obtain ⟨p, q, r, hq, -, hreal⟩ :=
    swierczkowski_first_letter_residue_invariant _ _ _ _ rfl rfl rfl rfl w hne
  rw [← hU_def] at hreal
  have hscale :=
    scaled_word_prod A AInv B BInv _ _ _ _ hA hAInv hB hBInv (FreeGroup.toWord w)
  rw [← hU_def] at hscale
  rw [hP] at hscale
  have hone : ((1/3 : ℝ) ^ (FreeGroup.toWord w).length • U).mulVec ![0, 1, 0] = ![0, 1, 0] := by
    rw [← hscale, Matrix.one_mulVec]
  have hmid := smul_mulvec_middle _ p q r U hreal hone
  have hdvd := three_dvd_of_pow_inv_mul _ q (List.length_pos_of_ne_nil hne) hmid
  exact hq hdvd

/-- If `f : α → G` has the property that every nonempty reduced word in `FreeGroup α` maps to a
nontrivial element of `G`, then `FreeGroup.lift f` is injective.

Injectivity is reduced to trivial kernel: `lift f w = 1 → w = 1`. Since `lift f w` equals the
word product over `toWord w` (via `FreeGroup.lift_mk`), a nontrivial `w` has `toWord w ≠ []`
and the hypothesis `h` then contradicts `lift f w = 1`. -/
theorem freegroup_lift_injective_of_word_prod_ne_one
    {α : Type*} [DecidableEq α] {G : Type*} [Group G] (f : α → G)
    (h : ∀ w : FreeGroup α, FreeGroup.toWord w ≠ [] →
        ((FreeGroup.toWord w).map
            (fun x : α × Bool => if x.2 then f x.1 else (f x.1)⁻¹)).prod ≠ 1) :
    Function.Injective (FreeGroup.lift f) := by
  have lift_eq_word_prod : ∀ w : FreeGroup α,
      (FreeGroup.lift f) w = ((FreeGroup.toWord w).map
        (fun x : α × Bool => if x.2 then f x.1 else (f x.1)⁻¹)).prod := by
    intro w
    conv_lhs => rw [← FreeGroup.mk_toWord (x := w)]
    rw [FreeGroup.lift_mk]
    congr 1
    apply List.map_congr_left
    intro x _
    cases x.2 <;> rfl
  rw [injective_iff_map_eq_one (FreeGroup.lift f)]
  intro w hw
  by_contra hne
  have hword : FreeGroup.toWord w ≠ [] := by
    intro hc
    exact hne (FreeGroup.toWord_injective (by rw [hc, FreeGroup.toWord_one]))
  exact h w hword (by rw [← lift_eq_word_prod w]; exact hw)

end Library.Geometry.BanachTarski.RotationWordNe1
