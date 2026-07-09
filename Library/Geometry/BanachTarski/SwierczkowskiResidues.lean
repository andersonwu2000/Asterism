import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Library.Geometry.BanachTarski.Defs

/-!
# Świerczkowski residue invariants

This file establishes the mod-3 residue invariant used in Świerczkowski's proof that
the rotation matrices $A$ and $B$ generate a free group of rank 2, a key step in the
Banach–Tarski paradox.

The central idea is to encode the action of the generators $A, A^{-1}, B, B^{-1}$ on the
lattice $\mathbb{Z}[\sqrt{2}]^3$ via an integer triple $(p, q, r)$, and to show that the
second coordinate $q$ of the result is never divisible by 3. This non-divisibility forces
the image vector to be nonzero, proving that no nontrivial reduced word maps $e_2$ to $e_2$.

## Main statements

- `swierczkowski_first_letter_residue_invariant`: for any non-empty reduced word `w` in
  `FreeGroup (Fin 2)`, the product of the corresponding generator matrices applied to
  `![0, 1, 0]` yields a vector $(\sqrt{2}\,p,\, q,\, \sqrt{2}\,r)$ where $3 \nmid q$,
  and the residue class of $(p, q, r)$ modulo 3 is determined by the first letter of `w`.

## Implementation notes

The step function `step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ` encodes how each
generator acts on the triple $(p, q, r)$ representing a vector $(\sqrt{2}\,p, q, \sqrt{2}\,r)$.
The invariant is propagated by induction on the length of the reduced word via
`residue_invariant_foldr_list`, with the arithmetic core isolated in `cons_residue_arith`.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.SwierczkowskiResidues

/-- Given matrices `a`, `aInv`, `b`, `bInv` equal to the standard Świerczkowski rotation
matrices and a step function `step` encoding their integer lattice action, a single
generator matrix applied to a vector $(\sqrt{2}\,p, q, \sqrt{2}\,r)$ yields
$(\sqrt{2}\,p', q', \sqrt{2}\,r')$ where $(p', q', r') = \mathtt{step}(x, (p, q, r))$. -/
theorem genmat_action_embed
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
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r)) :
    ∀ (x : Fin 2 × Bool) (v : ℤ × ℤ × ℤ),
      Matrix.mulVec
        (if x.1 = 0 then (if x.2 then a else aInv) else (if x.2 then b else bInv))
        ![(v.1 : ℝ) * Real.sqrt 2, (v.2.1 : ℝ), (v.2.2 : ℝ) * Real.sqrt 2]
      = ![((step x v).1 : ℝ) * Real.sqrt 2, ((step x v).2.1 : ℝ),
          ((step x v).2.2 : ℝ) * Real.sqrt 2] := by
  intro x v
  obtain ⟨p, q, r⟩ := v
  obtain ⟨xi, xb⟩ := x
  have hpow : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have h := hstep p q r
  obtain ⟨h0t, h0f, h1t, h1f⟩ := h
  subst ha haInv hb hbInv
  fin_cases xi <;> fin_cases xb <;>
  simp only [Fin.zero_eta, Fin.isValue, Fin.mk_one, Fin.reduceEq, Bool.false_eq_true,
             ite_false, ite_true] <;>
  simp only [h0t, h0f, h1t, h1f] <;>
  funext i <;> fin_cases i <;>
  simp only [Matrix.mulVec, Matrix.of_apply] <;>
  simp [Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.head_cons] <;>
  ring_nf <;>
  simp only [hpow] <;>
  ring

/-- The product of a list of generator matrices applied to `![0, 1, 0]` equals the vector
$(\sqrt{2}\,p, q, \sqrt{2}\,r)$ encoded by `List.foldr step (0, 1, 0)` applied to the
corresponding word, where `step` is the integer-lattice action of the generators. -/
theorem matrix_prod_realizes_triple
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

/-- For a single letter `x : Fin 2 × Bool`, applying `step` to `(0, 1, 0)` yields an
integer triple $(p, q, r)$ with $3 \nmid q$, and the residue class of $(p, q, r)$ modulo 3
is determined by `x`: specifically, the second coordinate is congruent to $\pm$ the first
or third, according to which generator `x` selects. -/
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

/-- The mod-3 residue invariant propagates through prepending one letter `x`, provided
`M` does not begin with the inverse of `x`. Case-splits on `x` and `hclass`; eliminates
the inverse-head case via `hhead`; closes non-divisibility and `ModEq` goals by `omega`. -/
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

/-- Propagates the mod-3 residue invariant through the cons step `x :: M` for a reduced
word. The reducedness condition `hred` prevents `M` from starting with the inverse of `x`,
which is exactly the hypothesis that `cons_residue_arith` requires. -/
theorem cons_residue_step
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (x : Fin 2 × Bool) (M : List (Fin 2 × Bool))
    (hred : FreeGroup.reduce (x :: M) = x :: M) (hne : M ≠ [])
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
        ((x :: M).head? = some (1, false) ∧ q' ≡ r'  [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) )  := by
  -- Reducedness of `x :: M` forbids `M` from starting with `x`'s inverse.
  have hhead : M.head? ≠ some (x.1, !x.2) := cons_head_ne_inv x M hred hne
  -- Pure arithmetic core: with the FreeGroup reduce equation replaced by the clean
  -- head-inequality, `step x` carries the head-keyed mod-3 invariant to `x :: M`.
  exact cons_residue_arith step hstep x M hhead p q r hfold hq hclass

/-- For any non-empty reduced word `L : List (Fin 2 × Bool)`, the foldr step from
`(0, 1, 0)` yields an integer triple $(p, q, r)$ with $3 \nmid q$, together with a
congruence class for $(p, q, r)$ modulo 3 determined by the head letter of `L`. -/
theorem residue_invariant_foldr_list
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (L : List (Fin 2 × Bool)) (hred : FreeGroup.reduce L = L) (hne : L ≠ []) :
    ∃ p q r : ℤ,
      ¬ (3 ∣ q) ∧
      ( (L.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ) ∧
      List.foldr step (0, 1, 0) L = (p, q, r)  := by
  revert hred hne
  induction L with
  | nil => intro _ hne; exact absurd rfl hne
  | cons x tl ih =>
    intro hred hne
    cases tl with
    | nil =>
      obtain ⟨p, q, r, hfold, hq, hclass⟩ := single_letter_residue_base step hstep x
      exact ⟨p, q, r, hq, hclass, hfold⟩
    | cons y tl' =>
      have htl_ne : (y :: tl') ≠ [] := by simp
      have htl_red := tail_of_reduced_is_reduced x (y :: tl') hred
      obtain ⟨p, q, r, hq, hclass, hfold⟩ := ih htl_red htl_ne
      obtain ⟨p', q', r', hfold', hq', hclass'⟩ :=
        cons_residue_step step hstep x (y :: tl') hred htl_ne p q r hfold hq hclass
      exact ⟨p', q', r', hq', hclass', hfold'⟩

/-- **Świerczkowski's first-letter residue invariant**: for any non-empty word `w` in
`FreeGroup (Fin 2)`, there exist integers $p, q, r$ with $3 \nmid q$ such that the
product of the generator matrices corresponding to `FreeGroup.toWord w`, applied to
`![0, 1, 0]`, equals $(\sqrt{2}\,p, q, \sqrt{2}\,r)$, and the residue class of
$(p, q, r)$ modulo 3 is determined by the first letter of `w`. -/
theorem swierczkowski_first_letter_residue_invariant
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

end Library.Geometry.BanachTarski.SwierczkowskiResidues
