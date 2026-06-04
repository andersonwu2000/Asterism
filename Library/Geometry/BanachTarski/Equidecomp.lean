import Library.Geometry.BanachTarski.TrigCountability
import Mathlib

open Library.Geometry.BanachTarski.TrigCountability
open Matrix

namespace Library.Geometry.BanachTarski.Equidecomp

-- Direct proof via `FreeGroup.reduce.cons`: rewrite `reduce (x :: L)` and use `hL` to
-- collapse `reduce L` to `L`, then case on `L`. The nil case is `simp`; the cons case
-- splits on the cancellation condition. The only content needing `hL` (reducedness) is
-- `h_reduced`: a reduced `hd :: tl` cannot have `tl` start with `hd`'s inverse — proved by
-- exhibiting the `Red.Step.not` cancellation and deriving a length contradiction from
-- `reduce.eq_of_red` + `Red.length`. Builds sorry-free; shipped as a leaf.
theorem reduce_cons_head_of_reduced {α : Type*} [DecidableEq α]
    (x : α × Bool) (L : List (α × Bool)) (hL : FreeGroup.reduce L = L) :
    (FreeGroup.reduce (x :: L)).head? = some x ↔ L.head? ≠ some (x.1, !x.2)  := by
  rw [FreeGroup.reduce.cons, hL]
  cases L with
  | nil => simp
  | cons hd tl =>
    have h_reduced : tl.head? ≠ some (hd.1, !hd.2) := by
      intro hcontra
      rw [List.head?_eq_some_iff] at hcontra
      obtain ⟨rest, hrest⟩ := hcontra
      subst hrest
      obtain ⟨c, e⟩ := hd
      have hstep : FreeGroup.Red.Step ((c, e) :: (c, !e) :: rest) rest :=
        @FreeGroup.Red.Step.not α [] rest c e
      have heq := FreeGroup.reduce.eq_of_red hstep.to_red
      simp only at hL heq
      rw [hL] at heq
      obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := rest))
      have hlen := congrArg List.length heq
      simp only [List.length_cons] at hlen
      omega
    obtain ⟨a, b⟩ := x
    obtain ⟨c, d⟩ := hd
    simp only [List.head?_cons]
    split_ifs with hcond
    · obtain ⟨rfl, rfl⟩ := hcond
      simpa [Bool.not_not] using h_reduced
    · simp only [List.head?_cons, Option.some.injEq, Prod.mk.injEq, true_iff, ne_eq, not_and]
      intro hc hd2
      exact hcond ⟨hc.symm, by rw [hd2, Bool.not_not]⟩

-- Strip the group layer, then reduce to a pure `reduce`-of-cons head fact.
-- `hmul` rewrites `(of i)⁻¹ * w` to `mk ((i,false) :: toWord w)` (via `inv_mk`/`mul_mk`)
-- so its `toWord` is `reduce ((i,false) :: toWord w)` — the group algebra is discharged inline.
-- The remaining content is the single sub-goal `reduce_cons_head_of_reduced`: for an already
-- reduced list `L`, prepending a letter `x` keeps `x` as head iff `L` does not start with `x`'s
-- inverse `(x.1, !x.2)`. Instantiated at `x = (i,false)`, `L = toWord w` (reduced by
-- `reduce_toWord`), `(x.1, !x.2) = (i, true)`, closing the parent.
theorem head_inv_mul_iff {α : Type*} [DecidableEq α] (i : α) (w : FreeGroup α) :
    (FreeGroup.toWord ((FreeGroup.of i)⁻¹ * w)).head? = some (i, false)
      ↔ (FreeGroup.toWord w).head? ≠ some (i, true)  := by
  have hmul : FreeGroup.toWord ((FreeGroup.of i)⁻¹ * w)
      = FreeGroup.reduce ((i, false) :: FreeGroup.toWord w) := by
    have hinv : (FreeGroup.of i)⁻¹ = FreeGroup.mk [(i, false)] := by
      rw [show (FreeGroup.of i) = FreeGroup.mk [(i, true)] from rfl, FreeGroup.inv_mk]; rfl
    conv_lhs => rw [hinv, ← FreeGroup.mk_toWord (x := w), FreeGroup.mul_mk]
    rw [FreeGroup.toWord_mk]; rfl
  rw [hmul]
  have h := reduce_cons_head_of_reduced (i, false) (FreeGroup.toWord w)
    (FreeGroup.reduce_toWord w)
  simpa using h

-- Direct proof (leaf): tail of a reduced word is reduced.
-- Rewrite `reduce (x :: M)` via `reduce.cons` and case on `reduce M`; the cancelling
-- branch contradicts `(reduce M).length ≤ M.length`, the other gives `reduce M = M`.
theorem tail_of_reduced_is_reduced {α : Type*} [DecidableEq α]
    (x : α × Bool) (M : List (α × Bool))
    (h : FreeGroup.reduce (x :: M) = x :: M) :
    FreeGroup.reduce M = M  := by
  rw [FreeGroup.reduce.cons] at h
  rcases hM : FreeGroup.reduce M with _ | ⟨hd, tl⟩
  · rw [hM] at h
    exact (List.cons.inj h).2
  · rw [hM] at h
    simp only at h
    split_ifs at h with hc
    · exfalso
      obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := M))
      rw [hM, h] at hn
      simp at hn
      omega
    · exact (List.cons.inj h).2

-- entry_kind: Builder
-- cons_head_ne_inv: a reduced list `x :: M` cannot have `M` start with `x`'s inverse;
-- proved by Red.Step.not cancellation + length contradiction via reduce.eq_of_red.
theorem cons_head_ne_inv (x : Fin 2 × Bool) (M : List (Fin 2 × Bool))
    (hred : FreeGroup.reduce (x :: M) = x :: M) (hne : M ≠ []) :
    M.head? ≠ some (x.1, !x.2) := by
  intro hcontra
  rw [List.head?_eq_some_iff] at hcontra
  obtain ⟨rest, hrest⟩ := hcontra
  subst hrest
  obtain ⟨c, e⟩ := x
  simp only at hred
  have hstep : FreeGroup.Red.Step ((c, e) :: (c, !e) :: rest) rest :=
    @FreeGroup.Red.Step.not (Fin 2) [] rest c e
  have heq := FreeGroup.reduce.eq_of_red hstep.to_red
  simp only at heq
  rw [hred] at heq
  obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := rest))
  have hlen := congrArg List.length heq
  simp only [List.length_cons] at hlen hn
  omega

-- entry_kind: Builder
theorem empty_word_head_eq_one : ∀ (w : FreeGroup (Fin 2)),
    (FreeGroup.toWord w).head? = none → w = 1 := by norm_num

-- (of 1)⁻¹^m reduces to the constant word `replicate m (1, false)`, whose head
-- (when nonempty) has first component 1 ≠ 0; the empty case (m = 0) is `none`.
-- Direct free-group computation: (of 1)⁻¹ = mk [(1,false)], so the power is
-- mk (replicate m (1,false)), and `reduce` fixes the already-reduced replicate.
theorem tower_first_letter_ne_zero : ∀ m : ℕ,
    ¬ (FreeGroup.toWord ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹ ^ m)).head?.map Prod.fst
      = some 0  := by
  intro m
  have hgen : ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹) = FreeGroup.mk [(1, false)] := by
    rw [FreeGroup.of, FreeGroup.inv_mk]; rfl
  have hred : ∀ k : ℕ,
      FreeGroup.reduce (List.replicate k (1, false) : List (Fin 2 × Bool))
        = List.replicate k (1, false) := by
    intro k
    induction k with
    | zero => rfl
    | succ k ih =>
      rw [List.replicate_succ, FreeGroup.reduce.cons, ih]
      cases k with
      | zero => rfl
      | succ j => rw [List.replicate_succ]; simp
  have hpow : ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹) ^ m
      = FreeGroup.mk (List.replicate m (1, false)) := by
    induction m with
    | zero => rfl
    | succ k ih =>
      rw [pow_succ, ih, hgen, FreeGroup.mul_mk, ← List.replicate_succ']
  have hw : FreeGroup.toWord ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹ ^ m)
      = List.replicate m (1, false) := by
    rw [hpow, FreeGroup.toWord_mk, hred]
  rw [hw]
  cases m with
  | zero => simp
  | succ n => simp [List.replicate_succ]

-- entry_kind: Builder
theorem length_pow_inv_of (k : ℕ) :
    (FreeGroup.toWord (((FreeGroup.of (1:Fin 2))⁻¹) ^ k)).length = k := by norm_num

-- entry_kind: Builder
theorem of_pow_ne_one : ∀ n : ℕ, 1 ≤ n → (FreeGroup.of (0 : Fin 2)) ^ n ≠ 1 := by aesop

-- `lift f` is injective ⇔ trivial kernel; reduce to `lift f w = 1 → w = 1`.
-- `lift f w` equals the product over `toWord w` (representation lemma, via `lift_mk`),
-- so if `w ≠ 1` then `toWord w ≠ []` and the hypothesis `h` forbids that product = 1.
theorem freegroup_lift_injective_of_word_prod_ne_one
    {α : Type*} [DecidableEq α] {G : Type*} [Group G] (f : α → G)
    (h : ∀ w : FreeGroup α, FreeGroup.toWord w ≠ [] →
        ((FreeGroup.toWord w).map
            (fun x : α × Bool => if x.2 then f x.1 else (f x.1)⁻¹)).prod ≠ 1) :
    Function.Injective (FreeGroup.lift f)  := by
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

-- Direct proof: `Aᵀ A = 1 ⟹ ⟪Ax, Ay⟫ = ⟪x, y⟫`. Expand both Euclidean inners
-- componentwise (`PiLp.inner_apply`), reduce `toEuclideanLin A` to `A.mulVec`, and
-- rewrite the real scalar inner `⟪a,b⟫_ℝ = a*b` (`hr`). The remaining sum is the
-- dot-product identity `(A*ᵥx) ⬝ᵥ (A*ᵥy) = x ⬝ᵥ y` (`key`), closed by
-- `dotProduct_mulVec`/`mulVec_transpose`/`mulVec_mulVec` + `hA` + `one_mulVec`.
theorem orthogonal_matrix_preserves_inner {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) (hA : Matrix.transpose A * A = 1) :
    ∀ x y : EuclideanSpace ℝ (Fin n),
      inner ℝ (Matrix.toEuclideanLin A x) (Matrix.toEuclideanLin A y) = inner ℝ x y  := by
  intro x y
  have key : (A.mulVec x.ofLp) ⬝ᵥ (A.mulVec y.ofLp) = x.ofLp ⬝ᵥ y.ofLp := by
    rw [Matrix.dotProduct_mulVec, ← Matrix.mulVec_transpose, Matrix.mulVec_mulVec, hA,
      Matrix.one_mulVec]
  have hr : ∀ a b : ℝ, inner ℝ a b = a * b := by
    intro a b
    have h := RCLike.inner_apply (𝕜 := ℝ) a b
    simp only [starRingEnd_apply, star_trivial] at h
    exact h.trans (mul_comm b a)
  rw [PiLp.inner_apply, PiLp.inner_apply]
  simp only [Matrix.toEuclideanLin_apply, WithLp.ofLp_toLp, hr]
  exact key

-- Decompose: orthogonal A → IsometryEquiv via a LinearIsometryEquiv, then `.toIsometryEquiv`.
-- One sub-goal: `orthogonal_matrix_preserves_inner` — `toEuclideanLin A` preserves the real inner
-- product (the orthogonality content: ⟪Ax,Ay⟫ = ⟪x,AᵀAy⟫ = ⟪x,y⟫). The rest is pure structural
-- packaging on top: `LinearMap.isometryOfInner` turns the inner-preservation into a `LinearIsometry`
-- f; f is injective hence (finite dim) surjective via `LinearMap.injective_iff_surjective`;
-- `LinearIsometryEquiv.ofSurjective` upgrades f to a `≃ₗᵢ`; `.toIsometryEquiv` is the witness, and
-- its action is defeq to `toEuclideanLin A` (rfl). The sub-goal is strictly simpler: a pure
-- inner-product/matrix identity, no existential or isometry packaging.
theorem orthogonal_matrix_isometry_equiv {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) (hA : Matrix.transpose A * A = 1) :
    ∃ e : EuclideanSpace ℝ (Fin n) ≃ᵢ EuclideanSpace ℝ (Fin n),
      ∀ x : EuclideanSpace ℝ (Fin n), e x = Matrix.toEuclideanLin A x  := by
  have h_inner := orthogonal_matrix_preserves_inner A hA
  let f : EuclideanSpace ℝ (Fin n) →ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n) :=
    (Matrix.toEuclideanLin A).isometryOfInner h_inner
  have hinj : Function.Injective f := f.injective
  have hsurj : Function.Surjective f := by
    have h := (LinearMap.injective_iff_surjective (f := f.toLinearMap))
    exact h.mp hinj
  let L := LinearIsometryEquiv.ofSurjective f hsurj
  refine ⟨L.toIsometryEquiv, ?_⟩
  intro x
  rfl

-- entry_kind: Builder
-- z_rotation_block_orthogonal: the 3×3 z-rotation block matrix satisfies Mᵀ·M = 1
-- Proved entry-by-entry using sin²+cos²=1.
theorem z_rotation_block_orthogonal (θ : ℝ) :
    Matrix.transpose
        (!![Real.cos θ, -Real.sin θ, 0;
            Real.sin θ,  Real.cos θ, 0;
            0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) *
      (!![Real.cos θ, -Real.sin θ, 0;
          Real.sin θ,  Real.cos θ, 0;
          0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) = 1 := by
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Matrix.transpose_apply, Fin.sum_univ_three,
          Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.cons_val'] <;>
    ring_nf <;>
    simp [Real.sin_sq_add_cos_sq, add_comm (Real.cos θ ^ 2) (Real.sin θ ^ 2)]

-- Direct leaf proof of the z-axis rotation composition law M(θ)·M(φ) = M(θ+φ).
-- Rewrite cos/sin of the sum via the angle-addition formulas, then check the 9
-- matrix entries: `ext` + `fin_cases` reduces to scalar `Fin.sum_univ_three`
-- products closed by `ring`. No sub-goals needed.
theorem z_rotation_matrix_mul_eq_add (θ φ : ℝ) :
    (!![Real.cos θ, -Real.sin θ, 0;
        Real.sin θ,  Real.cos θ, 0;
        0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) *
      !![Real.cos φ, -Real.sin φ, 0;
         Real.sin φ,  Real.cos φ, 0;
         0,           0,          1]
      = !![Real.cos (θ + φ), -Real.sin (θ + φ), 0;
           Real.sin (θ + φ),  Real.cos (θ + φ), 0;
           0,                 0,                1]  := by
  rw [Real.cos_add, Real.sin_add]
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Fin.sum_univ_three] <;> ring

-- Power law for the z-rotation block by induction on `n`, reusing the proved
-- multiplication law `z_rotation_matrix_mul_eq_add : M(α)·M(β) = M(α+β)`.
-- Base `n=0`: `M^0 = 1 = M(0)`. Step: `M^(k+1) = M^k·M = M(kθ)·M(θ) = M((k+1)θ)`.
theorem z_rotation_matrix_pow (θ : ℝ) (n : ℕ) :
    (!![Real.cos θ, -Real.sin θ, 0;
        Real.sin θ,  Real.cos θ, 0;
        0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) ^ n
      = !![Real.cos ((n : ℝ) * θ), -Real.sin ((n : ℝ) * θ), 0;
           Real.sin ((n : ℝ) * θ),  Real.cos ((n : ℝ) * θ), 0;
           0,                       0,                      1]  := by
  induction n with
  | zero =>
    simp only [pow_zero, Nat.cast_zero, zero_mul, Real.cos_zero, Real.sin_zero, neg_zero]
    ext i j
    fin_cases i <;> fin_cases j <;> simp
  | succ k ih =>
    rw [pow_succ, ih, z_rotation_matrix_mul_eq_add]
    have : ((k + 1 : ℕ) : ℝ) * θ = (k : ℝ) * θ + θ := by push_cast; ring
    rw [this]

-- entry_kind: Builder
-- x_rotation_block_orthogonal: the 3×3 x-rotation block matrix satisfies Mᵀ·M = 1
-- Proved entry-by-entry using sin²+cos²=1, mirroring z_rotation_block_orthogonal.
theorem x_rotation_block_orthogonal (φ : ℝ) :
    Matrix.transpose
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) *
      (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) = 1 := by
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Matrix.transpose_apply, Fin.sum_univ_three,
          Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.cons_val'] <;>
    ring_nf <;>
    simp [Real.sin_sq_add_cos_sq, add_comm (Real.cos φ ^ 2) (Real.sin φ ^ 2)]

-- a_inv_left_inverse: Matrix.mul_self_sqrt + fin_cases element-check closes AInv * A = 1
-- Substitute both definitions, establish sqrt2 * sqrt2 = 2, then verify each of the 9 entries
-- entry_kind: Builder
theorem a_inv_left_inverse (A AInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1/3:ℝ) • !![1, 2*Real.sqrt 2, 0; -2*Real.sqrt 2, 1, 0; 0, 0, 3]) :
    AInv * A = 1 := by
  subst hA hAInv
  have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Matrix.smul_apply, Fin.sum_univ_three] <;>
    ring_nf <;>
    nlinarith

-- b_inv_left_inverse: B-generator inverse satisfies BInv * B = 1 by elementwise nlinarith
-- Uses sqrt 2 ^ 2 = 2 to reduce each entry to a rational arithmetic check.
-- entry_kind: Builder
theorem b_inv_left_inverse (B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hB : B = (1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1])
    (hBInv : BInv = (1/3:ℝ) • !![3, 0, 0; 0, 1, 2*Real.sqrt 2; 0, -2*Real.sqrt 2, 1]) :
    BInv * B = 1 := by
  subst hB hBInv
  have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Fin.sum_univ_three, Matrix.cons_val',
          Matrix.cons_val_zero, Matrix.cons_val_one] <;>
    ring_nf <;> nlinarith [h2]

-- gen_a_det_one: det((1/3)•A) = 1 via Matrix.det_smul + explicit cofactor expansion + √2²=2
-- Uses rfl for third-row vector entries (Fin 3 index 2), simp for vecCons residual,
-- and nlinarith with hsq to close 3 + 12*(√2*√2) = 27.
theorem gen_a_det_one :
    ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 1 := by
  have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
  have hdet : (!![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 27 := by
    rw [Matrix.det_fin_three]
    have hv1 : (![1, -(2 * Real.sqrt 2), 0] : Fin 3 → ℝ) 2 = 0 := rfl
    have hv2 : (![2 * Real.sqrt 2, 1, 0] : Fin 3 → ℝ) 2 = 0 := rfl
    have hv3 : (![0, 0, 3] : Fin 3 → ℝ) 2 = 3 := rfl
    norm_num [hv1, hv2, hv3, Matrix.cons_val_succ, Matrix.cons_val_zero]
    have hc : Matrix.vecCons (0:ℝ)
        (fun i : Fin 2 ↦ Matrix.vecCons (0:ℝ) (fun _ : Fin 1 ↦ (3:ℝ)) i) (2:Fin 3) = 3 := by
      simp
    nlinarith [hsq, hc]
  have hsmul : ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det =
      (1/3:ℝ)^3 * (!![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det := Matrix.det_smul _ _
  rw [hsmul, hdet]
  norm_num

-- entry_kind: Builder
-- gen_b_det_one: det of (1/3)•B generator matrix = 1
theorem gen_b_det_one :
    ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 1 := by
  simp [Matrix.det_fin_three]
  ring_nf
  norm_num [Real.sq_sqrt]

-- T preserves W (W.map T ≤ W) and T is a linear equiv, so finrank is preserved;
-- in finite dimension a submodule contained in W with equal finrank IS W, hence
-- W.map T = W, so every w ∈ W has a preimage y ∈ W. Direct (no sub-goals).
theorem invariant_submodule_image_surj
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (T : F ≃ₗᵢ[ℝ] F) (W : Submodule ℝ F)
    (hW : ∀ x ∈ W, T x ∈ W) :
    ∀ w ∈ W, ∃ y ∈ W, T y = w  := by
  have hmap : W.map T.toLinearEquiv.toLinearMap ≤ W := by
    rintro x ⟨y, hy, rfl⟩
    exact hW y hy
  have hfin : Module.finrank ℝ (W.map T.toLinearEquiv.toLinearMap)
      = Module.finrank ℝ W := T.toLinearEquiv.finrank_map_eq W
  have heq : W.map T.toLinearEquiv.toLinearMap = W :=
    Submodule.eq_of_le_of_finrank_eq hmap hfin
  intro w hw
  rw [← heq] at hw
  obtain ⟨y, hy, hTy⟩ := hw
  exact ⟨y, hy, hTy⟩

-- t_conj_via_prodequiv: T equals its conjugate by prodEquivOfIsCompl — block-diagonal form
-- Proves T = e ∘ prodMap(T|W, T|W') ∘ e⁻¹ where e : W × W' ≃ₗ F is the IsCompl equivalence,
-- by showing T ∘ e = e ∘ prodMap (since T preserves W and W') then canceling e on the right.
-- entry_kind: Builder
theorem t_conj_via_prodequiv
    {𝕜 : Type*} [Field 𝕜] {F : Type*} [AddCommGroup F] [Module 𝕜 F]
    (T : F →ₗ[𝕜] F) (W W' : Submodule 𝕜 F)
    (hW : ∀ x ∈ W, T x ∈ W) (hW' : ∀ x ∈ W', T x ∈ W')
    (hcompl : IsCompl W W') :
    T = (Submodule.prodEquivOfIsCompl W W' hcompl).toLinearMap.comp
        ((LinearMap.prodMap (T.restrict hW) (T.restrict hW')).comp
          (Submodule.prodEquivOfIsCompl W W' hcompl).symm.toLinearMap) := by
  set e := W.prodEquivOfIsCompl W' hcompl
  set f := (T.restrict hW).prodMap (T.restrict hW')
  have hcomp : T.comp e.toLinearMap = e.toLinearMap.comp f := by
    apply LinearMap.ext
    rintro ⟨⟨w, hw⟩, ⟨w', hw'⟩⟩
    simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap]
    simp only [f, LinearMap.prodMap_apply, LinearMap.restrict_apply]
    change T (w + w') = T w + T w'
    exact map_add T w w'
  ext x
  have hx : T x = T (e (e.symm x)) := by rw [e.apply_symm_apply]
  rw [hx]
  have h2 : T (e (e.symm x)) = e (f (e.symm x)) := by
    have := congr($(hcomp) (e.symm x))
    simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap] at this
    exact this
  simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap, h2]

-- Block-diagonal determinant: F = W ⊕ W' with both T-invariant, so in a basis
-- adapted to the decomposition T is block-diagonal, giving det T = det(T|W)·det(T|W').
-- Realize this as conjugation by `Submodule.prodEquivOfIsCompl`: the sub-goal
-- `t_conj_via_prodequiv` says T equals e ∘ (T|W ×ₗ T|W') ∘ e.symm; then
-- `LinearMap.det_conj` strips the conjugation and `LinearMap.det_prodMap` splits the product.
theorem det_eq_prod_det_restrict_invariant
    {𝕜 : Type*} [Field 𝕜] {F : Type*} [AddCommGroup F] [Module 𝕜 F]
    [FiniteDimensional 𝕜 F]
    (T : F →ₗ[𝕜] F) (W W' : Submodule 𝕜 F)
    (hW : ∀ x ∈ W, T x ∈ W) (hW' : ∀ x ∈ W', T x ∈ W')
    (hbot : W ⊓ W' = ⊥) (htop : W ⊔ W' = ⊤) :
    LinearMap.det T
      = LinearMap.det (T.restrict hW) * LinearMap.det (T.restrict hW')  := by
  have hcompl : IsCompl W W' := ⟨disjoint_iff.mpr hbot, codisjoint_iff.mpr htop⟩
  have h_conj := t_conj_via_prodequiv T W W' hW hW' hcompl
  conv_lhs => rw [h_conj]
  rw [LinearMap.det_conj, LinearMap.det_prodMap]

-- endo_finrank_one_eq_smul_id: finrank-1 endomorphism is scalar multiple of id
-- Uses finrank_eq_one_iff_of_nonzero to get a spanning vector v, extracts c from f v = c • v,
-- then shows f x = c • x for all x via scalar decomposition x = r • v.
-- entry_kind: Builder
theorem endo_finrank_one_eq_smul_id
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F = 1) :
    ∃ c : ℝ, f = c • LinearMap.id := by
  have hpos : 0 < Module.finrank ℝ F := hfin ▸ Nat.one_pos
  obtain ⟨v, hv0⟩ : ∃ v : F, v ≠ 0 := by
    have := Module.nontrivial_of_finrank_pos hpos; exact exists_ne 0
  have htop : ℝ ∙ v = ⊤ := (finrank_eq_one_iff_of_nonzero v hv0).mp hfin
  have hspan : ∀ w : F, ∃ c : ℝ, c • v = w := fun w => by
    have hmem : w ∈ (ℝ ∙ v) := htop ▸ Submodule.mem_top
    exact Submodule.mem_span_singleton.mp hmem
  obtain ⟨c, hc⟩ := hspan (f v)
  refine ⟨c, LinearMap.ext fun x => ?_⟩
  obtain ⟨r, hr⟩ := hspan x
  simp only [LinearMap.smul_apply, LinearMap.id_apply]
  rw [← hr, map_smul, ← hc, smul_smul, smul_smul, mul_comm]

-- In a 1-dim space every endomorphism is a scalar c • id (sub-goal
-- `endo_finrank_one_eq_smul_id`). Then det f = c^finrank · det id = c (finrank=1),
-- and (c•id) x = c • x, closing f x = (det f) • x.
theorem endo_eq_det_smul_of_finrank_one
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F = 1) (x : F) :
    f x = (LinearMap.det f) • x  := by
  have h1 := endo_finrank_one_eq_smul_id f hfin
  obtain ⟨c, hc⟩ := h1
  rw [hc, LinearMap.det_smul, LinearMap.det_id, hfin, pow_one, mul_one]
  simp [LinearMap.smul_apply]

-- Split on finrank: 0 ⇒ F subsingleton ⇒ x = 0, both sides 0 (handled inline);
-- 1 ⇒ f is the scalar det f (single hard leaf). Combined by Nat.eq_zero_or_pos.
theorem endo_finrank_le_one_eq_det_smul
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F ≤ 1) (x : F) :
    f x = (LinearMap.det f) • x  := by
  rcases Nat.eq_zero_or_pos (Module.finrank ℝ F) with h0 | hpos
  · have hsub : Subsingleton F := Module.finrank_zero_iff.mp h0
    rw [Subsingleton.elim x 0, map_zero, smul_zero]
  · have h1 : Module.finrank ℝ F = 1 := le_antisymm hfin hpos
    exact endo_eq_det_smul_of_finrank_one f h1 x

-- Thin bridge over the proved scalar law `endo_finrank_le_one_eq_det_smul`:
-- restrict `T` to the ≤1-dim invariant `W`, so `T.restrict hinv : ↥W →ₗ ↥W`
-- acts as `(det) • ·`; `hdet` collapses the scalar to `1`, giving `T x = x` on `W`.
theorem det_one_isometry_finrank_le_one_submodule_eq_id
    {n : ℕ} (T : EuclideanSpace ℝ (Fin n) ≃ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n))
    (W : Submodule ℝ (EuclideanSpace ℝ (Fin n)))
    (hinv : ∀ x ∈ W, T x ∈ W)
    (hr : Module.finrank ℝ W ≤ 1)
    (hdet : LinearMap.det
      ((T : EuclideanSpace ℝ (Fin n) →ₗ[ℝ] EuclideanSpace ℝ (Fin n)).restrict hinv) = 1) :
    ∀ x ∈ W, T x = x  := by
  intro x hx
  have h := endo_finrank_le_one_eq_det_smul
    ((T : EuclideanSpace ℝ (Fin n) →ₗ[ℝ] EuclideanSpace ℝ (Fin n)).restrict hinv) hr ⟨x, hx⟩
  rw [hdet, one_smul] at h
  have h2 := congrArg Subtype.val h
  simpa [LinearMap.restrict_apply] using h2

-- A linear isometry equiv preserving a finite-dim submodule W also preserves Wᗮ.
-- Single sub-goal: T maps W *onto* W (injective + equal finrank ⇒ surjective onto W).
-- Closer: x ∈ Wᗮ, w ∈ W; write w = T y with y ∈ W, then ⟪w, T x⟫ = ⟪T y, T x⟫ =
-- ⟪y, x⟫ = 0 by inner_map_map and x ∈ Wᗮ. The onto-W fact is the only real work.
theorem isometry_fixed_complement_invariant
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (T : F ≃ₗᵢ[ℝ] F) (W : Submodule ℝ F)
    (hW : ∀ x ∈ W, T x ∈ W) :
    ∀ x ∈ Submodule.orthogonal W, T x ∈ Submodule.orthogonal W  := by
  have hsurj := invariant_submodule_image_surj T W hW
  intro x hx
  rw [Submodule.mem_orthogonal]
  intro w hw
  obtain ⟨y, hyW, rfl⟩ := hsurj w hw
  rw [T.inner_map_map]
  exact (Submodule.mem_orthogonal W x).mp hx y hyW

-- entry_kind: Builder
-- genmat_action_embed: matrix mulVec on embedded integer triple realizes the step function
-- Case-split on all 4 generators; substitute concrete matrix; rewrite step via hstep;
-- close each component with ring after ring_nf + simp [√2^2=2].
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
  simp only [Matrix.mulVec, Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.head_cons,
             Matrix.head_fin_const, Fin.isValue, Matrix.of_apply,
             Finset.sum_fin_eq_sum_range] <;>
  simp [Fin.sum_univ_three, Matrix.cons_val_zero, Matrix.cons_val_one,
        Matrix.head_cons] <;>
  push_cast <;>
  ring_nf <;>
  simp only [hpow] <;>
  ring

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

-- Prepend letter `x` to reduced nonempty tail `M`, carrying the head-keyed mod-3 residue
-- invariant from `M` to `x :: M`, via 2 strictly-simpler sub-goals.
--   `cons_head_ne_inv`     — FreeGroup combinatorics: a reduced `x :: M` cannot have `M`
--     start with `x`'s inverse `(x.1, !x.2)` (Red.Step.not cancellation + length).
--   `cons_residue_arith`   — pure ℤ/`Int.ModEq` core: with that head-inequality replacing
--     the FreeGroup reduce equation, `step x (p,q,r)` (= foldr over `x :: M`) satisfies the
--     head-keyed invariant; `hhead` + `hclass` + `¬3∣q` prune the residue state that would
--     make `3 ∣ q'`.
-- Combinator: derive `hhead` from reducedness, then hand the arithmetic the clean hypothesis.
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

-- Strip the FreeGroup wrapper and induct on the reduced word `L` from its leftmost
-- letter (the head, which `foldr` applies outermost), into 3 strictly-simpler sub-goals.
--   `single_letter_residue_base`   — single-letter words `[x]` satisfy the head-keyed
--     mod-3 residue invariant (a direct computation of `step x (0,1,0)` over 4 letters).
--   `tail_of_reduced_is_reduced`   — the tail of a reduced word is reduced, firing the IH.
--   `cons_residue_step`            — prepending a letter `x` to a reduced nonempty tail
--     whose head-keyed invariant holds yields the invariant for `x :: tail`, using
--     reducedness to prune impossible second-letter residue states.
-- Combinator is `induction L`: `nil` contradicts `hne`; the single-letter `cons … nil`
-- case is the base lemma; `cons … cons` threads the IH (on the reduced nonempty tail)
-- through the step lemma.  The sub-goals emit the conjuncts foldr-first, so each branch
-- re-associates `⟨…⟩` into this goal's `¬3∣q ∧ disj ∧ foldr` order.
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

-- Split off the per-letter matrix action as the single sub-goal `genmat_action_embed`
-- (each generator matrix on an embedded triple `![p√2,q,r√2]` realizes one `step`
-- recursion — no word, no induction). The combinator is a plain list induction folding
-- that bridge over `toWord w` (inlined rather than citing the proved general lemma
-- `s11395`/`matrix_prod_mulvec_realizes_foldr`, whose module is not auto-imported into a
-- strategy file unless it is a registered sub-goal); `hfold` then rewrites foldr to (p,q,r).
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

-- Factor the scalar `(1/3)` out of the word product by induction on the list.
-- Each generator equals `(1/3) •` its un-normalized integer matrix (hypotheses
-- `hA … hBInv`), so the head term `f x = (1/3) • g x` (via `← smul_ite` collecting
-- the branches), and the cons step combines `(r • _) * (s • _) = (r*s) • (_ * _)`
-- through `smul_mul_assoc`, `mul_smul_comm`, `smul_smul`, matching `pow_succ'`.
-- Direct leaf proof — no sub-goals.
theorem scaled_word_prod
    (A AInv B BInv MA MAInv MB MBInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3 : ℝ) • MA) (hAInv : AInv = (1/3 : ℝ) • MAInv)
    (hB : B = (1/3 : ℝ) • MB) (hBInv : BInv = (1/3 : ℝ) • MBInv)
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

-- smul_mulvec_middle: extract middle component from scaled mulVec identity;
-- uses Matrix.smul_mulVec to commute scalar, then congr_fun at index 1.
-- entry_kind: Builder

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

-- entry_kind: Builder
-- three_dvd_of_pow_inv_mul: if (1/3)^n * q = 1 in ℝ with n ≥ 1, then 3 ∣ q (as q = 3^n)
theorem three_dvd_of_pow_inv_mul (n : ℕ) (q : ℤ) (hn : 0 < n)
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

-- Freeness assembly: a reduced word's scaled rotation product cannot be the identity.
-- Each generator is `(1/3) • (unscaled integer matrix)`, so the word product is
-- `(1/3)^n • U` where `n = (toWord w).length ≥ 1` and `U` is the un-normalized product;
-- the proved residue invariant `s11396` gives integers `p q r` with `¬3∣q` and
-- `U.mulVec ![0,1,0] = ![p√2, q, r√2]`. If the product were `1`, the middle coordinate
-- forces `(1/3)^n * q = 1`, i.e. `q = 3^n`, divisible by 3 for `n ≥ 1` — contradicting `¬3∣q`.
-- Sub-goals: `scaled_word_prod` (factor `(1/3)^n` out of the list product, pure induction),
-- `smul_mulvec_middle` (extract the middle component of the scaled vector equation),
-- `three_dvd_of_pow_inv_mul` (the `(1/3)^n*q=1 → 3∣q` arithmetic). `s11396` is cited inline.
theorem rotation_word_ne_one_of_reduced
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1/3 : ℝ) • !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hB : B = (1/3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hBInv : BInv = (1/3 : ℝ) • !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1])
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    ((FreeGroup.toWord w).map
        (fun x : Fin 2 × Bool =>
          if x.1 = 0 then (if x.2 then A else AInv)
                     else (if x.2 then B else BInv))).prod
      ≠ (1 : Matrix (Fin 3) (Fin 3) ℝ)  := by
  intro hP
  have hne : FreeGroup.toWord w ≠ [] := fun h => hw (FreeGroup.toWord_eq_nil_iff.mp h)
  set U : Matrix (Fin 3) (Fin 3) ℝ :=
    ((FreeGroup.toWord w).map
        (fun x : Fin 2 × Bool =>
          if x.1 = 0 then (if x.2 then !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3]
                                  else !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3])
                     else (if x.2 then !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]
                                  else !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]))).prod
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

-- entry_kind: Builder
-- cos_pinned_by_components: solve 2×2 rotation linear system for cos via field algebra
-- p0*q0+p1*q1 = c*(p0²+p1²) after substituting the component equations; divide by nonzero norm.
theorem cos_pinned_by_components (c s p0 p1 q0 q1 : ℝ)
    (h0 : q0 = c * p0 - s * p1) (h1 : q1 = s * p0 + c * p1)
    (hp : ¬ (p0 = 0 ∧ p1 = 0)) :
    c = (p0 * q0 + p1 * q1) / (p0 ^ 2 + p1 ^ 2) := by
  have hne : p0 ^ 2 + p1 ^ 2 ≠ 0 := by
    intro h
    apply hp
    constructor
    · nlinarith [sq_nonneg p0, sq_nonneg p1]
    · nlinarith [sq_nonneg p0, sq_nonneg p1]
  rw [eq_div_iff hne, h0, h1]
  ring

-- entry_kind: Builder
-- uicc_uncountable: non-degenerate real interval has continuum cardinality, not countable
-- Uses Cardinal.mk_Icc_real to lift Set.uIcc a b (= Set.Icc (a⊓b) (a⊔b)) to continuum,
-- then contradicts Set.Countable via Cardinal.mk_le_aleph0_iff + aleph0_lt_continuum.
theorem uicc_uncountable (a b : ℝ) (hab : a ≠ b) : ¬ (Set.uIcc a b).Countable := by
  intro h
  have hlt : a ⊓ b < a ⊔ b := inf_lt_sup.mpr hab
  have hmk : Cardinal.mk ↑(Set.Icc (a ⊓ b) (a ⊔ b)) = Cardinal.continuum :=
    Cardinal.mk_Icc_real hlt
  have hcount : Cardinal.mk ↑(Set.Icc (a ⊓ b) (a ⊔ b)) ≤ Cardinal.aleph0 :=
    Cardinal.mk_le_aleph0_iff.mpr h
  exact absurd (hmk ▸ hcount) (not_le.mpr Cardinal.aleph0_lt_continuum)

-- A preconnected T ⊆ ℝ with two distinct points a, b is uncountable.
-- Preconnected ⇒ OrdConnected, so the nondegenerate interval uIcc a b ⊆ T
-- (inlined via hT.ordConnected.uIcc_subset). That interval is uncountable
-- (uicc_uncountable, the only sub-goal). If T were countable so would its
-- subset uIcc a b — contradiction.
theorem preconnected_real_two_points_uncountable (T : Set ℝ) (hT : IsPreconnected T)
    (a b : ℝ) (ha : a ∈ T) (hb : b ∈ T) (hab : a ≠ b) : ¬ T.Countable  := by
  intro hc
  have h_subset : Set.uIcc a b ⊆ T := hT.ordConnected.uIcc_subset ha hb
  have h_unc : ¬ (Set.uIcc a b).Countable := uicc_uncountable a b hab
  exact h_unc (hc.mono h_subset)

-- Reduce uncountability of a preconnected two-point set to the real-line case
-- via the continuous map x ↦ dist x p: its image is preconnected, contains 0 and
-- dist q p (distinct, since p ≠ q), so the abstract ℝ lemma makes the image
-- uncountable; were S countable the image would be countable — contradiction.
theorem preconnected_two_points_uncountable {X : Type*} [MetricSpace X] {S : Set X}
    {p q : X} (h : IsPreconnected S) (hp : p ∈ S) (hq : q ∈ S) (hpq : p ≠ q) :
    ¬ S.Countable  := by
  intro hc
  have hcont : Continuous (fun x => dist x p) := by fun_prop
  have hT : IsPreconnected ((fun x => dist x p) '' S) := h.image _ hcont.continuousOn
  have hcountT : ((fun x => dist x p) '' S).Countable := hc.image _
  have ha : (0:ℝ) ∈ (fun x => dist x p) '' S := ⟨p, hp, by simp⟩
  have hb : dist q p ∈ (fun x => dist x p) '' S := ⟨q, hq, rfl⟩
  have hab : (0:ℝ) ≠ dist q p := by
    simp only [ne_eq, eq_comm (a := (0:ℝ)), dist_eq_zero]
    exact fun h => hpq h.symm
  exact preconnected_real_two_points_uncountable _ hT 0 (dist q p) ha hb hab hcountT

-- orbit_section_general: pure choice-axiom orbit section for any MulAction —
-- uses Quotient.out on orbitRel to pick canonical reps constant on orbits
theorem orbit_section_general {G : Type*} [Group G] {α : Type*} [MulAction G α] :
    ∃ (rep : α → α) (wrd : α → G),
      (∀ x, wrd x • rep x = x) ∧
      (∀ x (w : G), rep (w • x) = rep x) := by
  classical
  let setoid := MulAction.orbitRel G α
  let rep : α → α := fun x => (Quotient.mk' (s := setoid) x).out
  have hmem : ∀ x : α, ∃ g : G, g • rep x = x := by
    intro x
    have heq : (Quotient.mk' (s := setoid) (rep x)) = Quotient.mk' x := Quotient.out_eq _
    rw [Quotient.eq'] at heq
    -- heq : ∃ g, g • x = rep x
    obtain ⟨g, hg⟩ := heq
    exact ⟨g⁻¹, by rw [← hg, inv_smul_smul]⟩
  have hrep : ∀ (x : α) (w : G), rep (w • x) = rep x := by
    intro x w
    simp only [rep]
    congr 1
    apply Quotient.sound
    simp only [MulAction.orbitRel_apply]
    exact MulAction.mem_orbit x w
  refine ⟨rep, fun x => (hmem x).choose, ?_, hrep⟩
  exact fun x => (hmem x).choose_spec

abbrev E : Type := EuclideanSpace ℝ (Fin 3)

/-- The self-isometry group of `E = ℝ³` acts on `E` by function application.
    mathlib provides `Group (α ≃ᵢ α)`; this `MulAction` instance bridges to
    `Equidecomp`, whose `IsDecompOn` predicate requires `[SMul G X]`. -/
noncomputable instance : SMul (E ≃ᵢ E) E := ⟨fun g x => g x⟩

noncomputable instance : MulAction (E ≃ᵢ E) E where
  one_smul _ := rfl
  mul_smul _ _ _ := rfl

-- letter0_head_flip: applies hwrd then head_inv_mul_iff to close the head-character flip
theorem letter0_head_flip
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x)
    (z : E) (hz : z ∈ M) :
    (FreeGroup.toWord (wrd (φ ((FreeGroup.of 0)⁻¹) • z))).head? = some (0, false)
      ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (0, true) := by
  rw [hwrd z hz]
  exact head_inv_mul_iff 0 (wrd z)

-- Direct ℕ-induction bridging isometry-power to matrix-power (no sub-goals).
-- `induction n generalizing x`; base `simp` (e^0 = id, A^0 = 1). Step: `pow_succ`
-- on both sides, `change` exposes `(e^k * e) x` as `(e^k) (e x)` (defeq), rewrite
-- `he` then the IH, and `Matrix.toLpLin_apply`/`mulVec_mulVec` collapse
-- `toEuclideanLin (A^k) ∘ toEuclideanLin A = toEuclideanLin (A^k * A)`.
theorem isometry_pow_realizes_matrix_pow
    (e : E ≃ᵢ E) (A : Matrix (Fin 3) (Fin 3) ℝ)
    (he : ∀ x : E, e x = Matrix.toEuclideanLin A x) (n : ℕ) (x : E) :
    (e ^ n) x = Matrix.toEuclideanLin (A ^ n) x  := by
  induction n generalizing x with
  | zero => simp
  | succ k ih =>
    rw [pow_succ, pow_succ]
    change (e ^ k) (e x) = _
    rw [he, ih]
    simp only [Matrix.toLpLin_apply, Matrix.mulVec_mulVec]

-- Mazur–Ulam: a 0-fixing isometry equivalence of a real normed space is ℝ-linear.
-- Promote `g` to the linear isometry equivalence `L := g.toRealLinearIsometryEquivOfMapZero hg`,
-- whose `map_smul` gives `L (r•x) = r • L x`; rewrite `⇑L = ⇑g` via the coe lemma. Direct, no sub-goals.
theorem isometry_fixing_origin_smul_comm
    (g : E ≃ᵢ E) (hg : g 0 = 0) (r : ℝ) (x : E) :
    g (r • x) = r • g x  := by
  have hmap := (g.toRealLinearIsometryEquivOfMapZero hg).map_smul r x
  rw [g.coe_toRealLinearIsometryEquivOfMapZero hg] at hmap
  exact hmap

-- Contrapositive route: assume `1 < finrank V` (V = ker(T-id), the fixed subspace).
-- V is T-invariant; so is its orthogonal complement Vᗮ (s11421). det T splits as
-- det(T|V)·det(T|Vᗮ) (s11422); det(T|V)=1 (T is id on V) and det T = 1 give det(T|Vᗮ)=1.
-- finrank V ≥ 2 ⇒ finrank Vᗮ ≤ 1, so the det-1 isometry T|Vᗮ is id (s11427), i.e. T fixes Vᗮ.
-- That collapses to T = refl (Vᗮ ⊆ V ∩ Vᗮ = 0 ⇒ Vᗮ = 0 ⇒ V = ⊤), contradicting hne.
theorem rotation_eigenspace_one_finrank_le_one
    (T : E ≃ₗᵢ[ℝ] E)
    (hdet : LinearMap.det (T.toLinearEquiv.toLinearMap) = 1)
    (hne : T ≠ LinearIsometryEquiv.refl ℝ E) :
    Module.finrank ℝ (LinearMap.ker (T.toLinearEquiv.toLinearMap - LinearMap.id)) ≤ 1  := by
  set L := T.toLinearEquiv.toLinearMap with hL
  -- `x` is fixed by `T` iff it lies in the kernel of `L - id`.
  have hmem : ∀ x : E, x ∈ LinearMap.ker (L - LinearMap.id) ↔ T x = x := by
    intro x
    rw [LinearMap.mem_ker, LinearMap.sub_apply, LinearMap.id_apply, sub_eq_zero]
    constructor <;> intro h <;> simpa [hL] using h
  by_contra hcon
  rw [not_le] at hcon
  set V := LinearMap.ker (L - LinearMap.id) with hV
  -- (1) the fixed subspace is `T`-invariant (in fact `T` acts as the identity on it).
  have hVinv : ∀ x ∈ V, T x ∈ V := by
    intro x hx
    rw [(hmem x).mp hx]
    exact hx
  -- (2) its orthogonal complement is `T`-invariant (proved sibling s11421).
  have hPinv : ∀ x ∈ Vᗮ, T x ∈ Vᗮ := isometry_fixed_complement_invariant T V hVinv
  have hbot : V ⊓ Vᗮ = ⊥ := Submodule.inf_orthogonal_eq_bot V
  have htop : V ⊔ Vᗮ = ⊤ := Submodule.sup_orthogonal_of_hasOrthogonalProjection
  -- (3) determinant splits over the invariant decomposition (proved sibling s11422).
  have hsplit := det_eq_prod_det_restrict_invariant L V Vᗮ hVinv hPinv hbot htop
  -- (4) `T` is the identity on `V`, so `det (T|V) = 1`.
  have hdetV : LinearMap.det (L.restrict hVinv) = 1 := by
    have hid : L.restrict hVinv = LinearMap.id := by
      refine LinearMap.ext fun y => ?_
      apply Subtype.ext
      have hy : T (y : E) = (y : E) := (hmem _).mp y.2
      simp only [LinearMap.restrict_apply, LinearMap.id_coe, id_eq]
      simpa [hL] using hy
    rw [hid, LinearMap.det_id]
  -- (5) hence `det (T|Vᗮ) = 1`.
  have hdetP : LinearMap.det (L.restrict hPinv) = 1 := by
    rw [hdetV, hdet] at hsplit; linarith
  -- (6) `finrank V ≥ 2` forces `finrank Vᗮ ≤ 1` in `ℝ³`.
  have hPle : Module.finrank ℝ (Vᗮ) ≤ 1 := by
    have hadd := Submodule.finrank_add_finrank_orthogonal (K := V)
    have h3 : Module.finrank ℝ E = 3 := finrank_euclideanSpace_fin
    omega
  -- (7) a det-1 isometry on a ≤1-dim invariant subspace is the identity (proved sibling s11427).
  have hfix : ∀ x ∈ Vᗮ, T x = x :=
    det_one_isometry_finrank_le_one_submodule_eq_id T Vᗮ hPinv hPle hdetP
  -- (8) collapse: `Vᗮ` is fixed ⇒ `Vᗮ ≤ V`, but `V ⊓ Vᗮ = ⊥`, so `Vᗮ = ⊥` and `V = ⊤`.
  have hsub : Vᗮ ≤ V := fun x hx => (hmem x).mpr (hfix x hx)
  have hVperp_bot : Vᗮ = ⊥ := by
    rw [eq_bot_iff, ← hbot]
    exact le_inf hsub le_rfl
  have hVtop : V = ⊤ := Submodule.orthogonal_eq_bot_iff.mp hVperp_bot
  -- (9) `T` then fixes every vector, i.e. `T = refl`, contradicting `hne`.
  apply hne
  refine LinearIsometryEquiv.ext (fun x => ?_)
  have hxV : x ∈ V := by rw [hVtop]; exact Submodule.mem_top
  rw [(hmem x).mp hxV]
  rfl

-- Direct (leaf) proof: finrank ℝ W ≤ 1 ⇒ via `finrank_le_one_iff` every x ∈ W is c • v
-- for a fixed v. A unit-norm c • v forces ‖c‖ * ‖v‖ = 1, i.e. c = ±‖v‖⁻¹, so the
-- sphere∩W set is contained in the 2-point set {‖v‖⁻¹ • v, -‖v‖⁻¹ • v}, hence finite.
theorem sphere_inter_finrank_le_one_finite
    (W : Submodule ℝ E) (hW : Module.finrank ℝ W ≤ 1) :
    {x ∈ Metric.sphere (0 : E) 1 | x ∈ W}.Finite  := by
  have h1 : ∃ v : E, ∀ x ∈ W, ∃ c : ℝ, x = c • v := by
    obtain ⟨v, hv⟩ := (finrank_le_one_iff (K := ℝ) (V := ↥W)).mp hW
    refine ⟨(v : E), fun x hx => ?_⟩
    obtain ⟨c, hc⟩ := hv ⟨x, hx⟩
    exact ⟨c, by simpa using congrArg (Subtype.val) hc.symm⟩
  obtain ⟨v, hv⟩ := h1
  apply Set.Finite.subset (s := {(‖v‖⁻¹ : ℝ) • v, (-(‖v‖⁻¹) : ℝ) • v})
  · exact (Set.finite_singleton _).insert _
  · intro x hx
    simp only [Set.mem_setOf_eq, Metric.mem_sphere, dist_eq_norm, sub_zero] at hx
    obtain ⟨hnorm, hxW⟩ := hx
    obtain ⟨c, rfl⟩ := hv x hxW
    rw [norm_smul, Real.norm_eq_abs] at hnorm
    have hc : |c| = ‖v‖⁻¹ := by
      rw [mul_comm] at hnorm; exact eq_inv_of_mul_eq_one_right hnorm
    rw [Set.mem_insert_iff, Set.mem_singleton_iff]
    rcases (abs_eq (by positivity)).mp hc with h | h
    · exact Or.inl (by rw [h])
    · exact Or.inr (by rw [h])

-- rotation_fixed_set_on_sphere_finite: fixed points of non-trivial det-1 isometry on sphere
-- are finite; cite rotation_eigenspace_one_finrank_le_one (finrank ker(T-id) ≤ 1) and
-- sphere_inter_finrank_le_one_finite (sphere ∩ finrank-≤1 submodule is finite), then subset.
-- entry_kind: Backward
theorem rotation_fixed_set_on_sphere_finite
    (T : E ≃ₗᵢ[ℝ] E)
    (hdet : LinearMap.det (T.toLinearEquiv.toLinearMap) = 1)
    (hT : T ≠ LinearIsometryEquiv.refl ℝ E) :
    {x ∈ Metric.sphere (0 : E) 1 | T x = x}.Finite := by
  set V := LinearMap.ker (T.toLinearEquiv.toLinearMap - LinearMap.id)
  have hV : Module.finrank ℝ V ≤ 1 :=
    rotation_eigenspace_one_finrank_le_one T hdet hT
  apply Set.Finite.subset (sphere_inter_finrank_le_one_finite V hV)
  rintro x ⟨hx_sph, hTx⟩
  refine ⟨hx_sph, ?_⟩
  rw [LinearMap.mem_ker, LinearMap.sub_apply, LinearMap.id_apply, sub_eq_zero]
  exact hTx

-- gen_word_prod_ne_one: transports matrix-level non-identity (hword) to isometry-product ≠ 1
-- via map_list_prod; bridges mat((g i)⁻¹) = AInv/BInv using Matrix.inv_eq_right_inv
-- applied to the right-inverse identity mat(g i) * mat((g i)⁻¹) = 1 from map_mul + map_one.
-- entry_kind: Builder
theorem gen_word_prod_ne_one

    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hinj : Function.Injective mat)
    (hg0 : mat (g 0) = A) (hg0inv : (mat (g 0))⁻¹ = AInv)
    (hg1 : mat (g 1) = B) (hg1inv : (mat (g 1))⁻¹ = BInv)
    (hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then A else AInv)
                    else (if x.2 then B else BInv))).prod ≠ 1) :
    ∀ v : FreeGroup (Fin 2), FreeGroup.toWord v ≠ [] →
      ((FreeGroup.toWord v).map (fun x : Fin 2 × Bool =>
        if x.2 then g x.1 else (g x.1)⁻¹)).prod ≠ 1 := by

  intro v hv
  have hv1 : v ≠ 1 := fun h => hv (FreeGroup.toWord_eq_nil_iff.mpr h)
  intro hcontra
  apply hword v hv1
  have mat_inv_g0 : mat ((g 0)⁻¹) = AInv := by
    have h : mat (g 0) * mat ((g 0)⁻¹) = 1 := by
      rw [← map_mul, mul_inv_cancel, map_one]
    rw [← hg0inv]; exact (Matrix.inv_eq_right_inv h).symm
  have mat_inv_g1 : mat ((g 1)⁻¹) = BInv := by
    have h : mat (g 1) * mat ((g 1)⁻¹) = 1 := by
      rw [← map_mul, mul_inv_cancel, map_one]
    rw [← hg1inv]; exact (Matrix.inv_eq_right_inv h).symm
  have key : ∀ x : Fin 2 × Bool,
      mat (if x.2 then g x.1 else (g x.1)⁻¹) =
      if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv) := by
    intro ⟨i, b⟩
    fin_cases i <;> fin_cases b <;>
      simp only [Fin.zero_eta, Fin.reduceEq, ↓reduceIte, Fin.mk_one, Bool.false_eq_true]
    · exact hg0
    · exact mat_inv_g0
    · exact hg1
    · exact mat_inv_g1


  have hbridge : mat ((FreeGroup.toWord v).map
      (fun x : Fin 2 × Bool => if x.2 then g x.1 else (g x.1)⁻¹)).prod =
      ((FreeGroup.toWord v).map (fun x : Fin 2 × Bool =>
      if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv))).prod := by
    rw [map_list_prod, List.map_map]
    congr 1
    apply List.map_congr_left
    intro x _
    exact key x
  rw [← hbridge, hcontra, map_one]

-- Build `mat` as the standard-basis matrix functor on the underlying linear maps:
--   mat T := LinearMap.toMatrix b b T.toLinearEquiv.toLinearMap,   b = (EuclideanSpace.basisFun …).toBasis.
-- The MonoidHom laws come from the End↔Matrix linear functor: `T ↦ T.toLinearEquiv.toLinearMap`
-- carries 1↦1 and (T₁*T₂)↦(·)*(·) (both `ext x; rfl`), then `LinearMap.toMatrix_one`/`toMatrix_mul`.
-- Injectivity: `LinearMap.toMatrix b b` is a LinearEquiv (injective) precomposed with the injective
--   coercions `LinearEquiv.toLinearMap_injective`/`LinearIsometryEquiv.toLinearEquiv_injective`.
-- det compatibility: `LinearMap.det_toMatrix`. Computation rule: `(LinearMap.toMatrix b b).symm`
--   is defeq `Matrix.toEuclideanLin`, so `LinearEquiv.eq_symm_apply … |>.mp rfl` reads off the matrix.
-- Sorry-free; ships as a leaf.
theorem matrix_rep_monoid_hom :
    ∃ mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ,
      Function.Injective mat ∧
      (∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap)) ∧
      (∀ (T : E ≃ₗᵢ[ℝ] E) (M : Matrix (Fin 3) (Fin 3) ℝ),
          (∀ x : E, T x = Matrix.toEuclideanLin M x) → mat T = M)  := by
  set b := (EuclideanSpace.basisFun (Fin 3) ℝ).toBasis with hb
  refine ⟨{
    toFun := fun T => LinearMap.toMatrix b b T.toLinearEquiv.toLinearMap
    map_one' := by
      have : ((1 : E ≃ₗᵢ[ℝ] E).toLinearEquiv.toLinearMap) = 1 := by ext x; rfl
      rw [this, LinearMap.toMatrix_one]
    map_mul' := by
      intro T₁ T₂
      have : ((T₁ * T₂).toLinearEquiv.toLinearMap)
          = (T₁.toLinearEquiv.toLinearMap) * (T₂.toLinearEquiv.toLinearMap) := by ext x; rfl
      rw [this, LinearMap.toMatrix_mul]
  }, ?_, ?_, ?_⟩
  · intro T₁ T₂ h
    simp only [MonoidHom.coe_mk, OneHom.coe_mk] at h
    have h2 : (T₁.toLinearEquiv.toLinearMap) = (T₂.toLinearEquiv.toLinearMap) :=
      (LinearMap.toMatrix b b).injective h
    have h3 : T₁.toLinearEquiv = T₂.toLinearEquiv := LinearEquiv.toLinearMap_injective h2
    exact LinearIsometryEquiv.toLinearEquiv_injective h3
  · intro T
    simp only [MonoidHom.coe_mk, OneHom.coe_mk]
    exact LinearMap.det_toMatrix b _
  · intro T M hTM
    simp only [MonoidHom.coe_mk, OneHom.coe_mk]
    have : T.toLinearEquiv.toLinearMap = Matrix.toEuclideanLin M :=
      LinearMap.ext fun x => hTM x
    rw [this]
    exact (LinearEquiv.eq_symm_apply (LinearMap.toMatrix b b)).mp rfl

-- orthogonal_to_linear_isometry_equiv: promote orthogonal M to LinearIsometryEquiv via
-- inner-product preservation → norm preservation → LinearIsometry → surjectivity (fin-dim).
-- entry_kind: Backward
theorem orthogonal_to_linear_isometry_equiv
    (M : Matrix (Fin 3) (Fin 3) ℝ) (hM : Matrix.transpose M * M = 1) :
    ∃ e : E ≃ₗᵢ[ℝ] E, ∀ x : E, e x = Matrix.toEuclideanLin M x := by
  have h_inner : ∀ x y : E,
      inner ℝ (Matrix.toEuclideanLin M x) (Matrix.toEuclideanLin M y) = inner ℝ x y :=
    orthogonal_matrix_preserves_inner M hM
  have hnorm : ∀ x : E, ‖Matrix.toEuclideanLin M x‖ = ‖x‖ := by
    intro x
    have := h_inner x x
    simp only [real_inner_self_eq_norm_sq] at this
    nlinarith [norm_nonneg (Matrix.toEuclideanLin M x), norm_nonneg x]
  let f : E →ₗᵢ[ℝ] E := ⟨Matrix.toEuclideanLin M, hnorm⟩
  have hinj : Function.Injective f.toLinearMap := f.injective
  have hsurj : Function.Surjective f.toLinearMap := by
    apply (f.toLinearMap.injective_iff_surjective_of_finrank_eq_finrank _).mp hinj
    rfl
  exact ⟨LinearIsometryEquiv.ofSurjective f hsurj, fun x => rfl⟩

-- Direct proof (leaf-bypass): `Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))`
-- is a monoid hom `FreeGroup (Fin 2) →* ℝ`; show it is ≡ 1 by free-group induction
-- (generators have det 1 via hdetA/hdetB; closed under one/mul/inv), then transport
-- the value back to `LinearMap.det` of the lift via hmatdet.
theorem lift_det_one
    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (hmatdet : ∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap))
    (hdetA : (mat (g 0)).det = 1) (hdetB : (mat (g 1)).det = 1)
    (w : FreeGroup (Fin 2)) :
    LinearMap.det ((FreeGroup.lift g w).toLinearEquiv.toLinearMap) = 1  := by
  have key : ∀ v : FreeGroup (Fin 2),
      (Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))) v = 1 := by
    intro v
    induction v using FreeGroup.induction_on with
    | C1 => simp
    | of x => fin_cases x <;> simp [hdetA, hdetB]
    | inv_of x ih =>
        have h2 := (Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))).map_mul
          (FreeGroup.of x)⁻¹ (FreeGroup.of x)
        simp only [inv_mul_cancel, map_one, ih, mul_one] at h2
        exact h2.symm
    | mul x y ihx ihy => rw [map_mul, ihx, ihy, mul_one]
  rw [← hmatdet]
  exact key w

-- Reduce `lift g w ≠ 1` to injectivity of `lift g`: sibling
-- `freegroup_lift_injective_of_word_prod_ne_one` (s11411) gives `Injective (lift g)` from a
-- per-word G-product-≠-1 hypothesis, so `lift g w = 1 = lift g 1` would force `w = 1`.
-- The one sub-goal `gen_word_prod_ne_one` transports `hword`'s matrix-product fact to the
-- needed G-product fact through the injective monoid hom `mat`.
theorem lift_ne_one
    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hinj : Function.Injective mat)
    (hg0 : mat (g 0) = A) (hg0inv : (mat (g 0))⁻¹ = AInv)
    (hg1 : mat (g 1) = B) (hg1inv : (mat (g 1))⁻¹ = BInv)
    (hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then A else AInv)
                    else (if x.2 then B else BInv))).prod ≠ 1)
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    FreeGroup.lift g w ≠ 1  := by
  have hgprod := gen_word_prod_ne_one g mat A AInv B BInv hinj hg0 hg0inv hg1 hg1inv hword
  have hinjlift : Function.Injective (FreeGroup.lift g) :=
    freegroup_lift_injective_of_word_prod_ne_one g hgprod
  intro hc
  exact hw (hinjlift (by rw [hc, map_one]))

-- Realize the two SO(3) generators through an abstract matrix-representation monoid hom.
--   • matrix_rep_monoid_hom: an injective, det-preserving `mat : (E ≃ₗᵢ E) →* Matrix` plus the
--     computation rule `hcomp` reading off the matrix of any isometry acting as `toEuclideanLin M`.
--   • orthogonal_to_linear_isometry_equiv: every orthogonal matrix is the action of some
--     `e : E ≃ₗᵢ[ℝ] E` (the `≃ₗᵢ` analogue of the proved `s11390`).
-- Orthogonality `Mᵀ * M = 1` of the two concrete generators is the cheap √2 computation, inlined.
-- Then g := ![eA, eB]; hcomp turns the actions into `mat (g i) = A/B`, and
-- a_inv_left_inverse/b_inv_left_inverse + `Matrix.inv_eq_left_inv` turn these into the inverse
-- literals. Each sub-goal is strictly simpler: an abstract reusable construction or a pure
-- matrix identity, with no entanglement between the hom and the generators.
theorem so3_realization_hom :
    ∃ (g : Fin 2 → (E ≃ₗᵢ[ℝ] E)) (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ),
      Function.Injective mat ∧
      (∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap)) ∧
      mat (g 0) = (1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] ∧
      (mat (g 0))⁻¹ = (1/3:ℝ) • !![1, 2*Real.sqrt 2, 0; -2*Real.sqrt 2, 1, 0; 0, 0, 3] ∧
      mat (g 1) = (1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1] ∧
      (mat (g 1))⁻¹ = (1/3:ℝ) • !![3, 0, 0; 0, 1, 2*Real.sqrt 2; 0, -2*Real.sqrt 2, 1]  := by
  have hoA : Matrix.transpose ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3])
      * ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3]) = 1 := by
    have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
    ext i j
    fin_cases i <;> fin_cases j <;>
      simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply] <;>
      nlinarith [h2]
  have hoB : Matrix.transpose ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1])
      * ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1]) = 1 := by
    have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
    ext i j
    fin_cases i <;> fin_cases j <;>
      simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply,
            Matrix.cons_val_zero, Matrix.cons_val_one] <;>
      ring_nf <;>
      nlinarith [hsq, sq_nonneg (Real.sqrt 2)]
  obtain ⟨mat, hinj, hdet, hcomp⟩ := matrix_rep_monoid_hom
  obtain ⟨eA, heA⟩ := orthogonal_to_linear_isometry_equiv _ hoA
  obtain ⟨eB, heB⟩ := orthogonal_to_linear_isometry_equiv _ hoB
  refine ⟨![eA, eB], mat, hinj, hdet, ?_, ?_, ?_, ?_⟩
  · change mat eA = _
    exact hcomp eA _ heA
  · change (mat eA)⁻¹ = _
    rw [hcomp eA _ heA]
    exact Matrix.inv_eq_left_inv (a_inv_left_inverse _ _ rfl rfl)
  · change mat eB = _
    exact hcomp eB _ heB
  · change (mat eB)⁻¹ = _
    rw [hcomp eB _ heB]
    exact Matrix.inv_eq_left_inv (b_inv_left_inverse _ _ rfl rfl)

-- Build ψ := FreeGroup.lift g, where g : Fin 2 → (E ≃ₗᵢ[ℝ] E) are the two rotation
-- generators realized through a monoid hom `mat` to 3×3 matrices (the SO(3) embedding).
-- so3_realization_hom supplies g, mat (injective, det-preserving) with mat(g i)/(mat(g i))⁻¹
-- equal to the four concrete generator matrices. Then per nontrivial word w:
--   • det = 1: mat preserves det and every generator-matrix has det 1  (lift_det_one)
--   • ψ w ≠ refl(=1): the matrix word-product ≠ 1 (rotation_word_ne_one_of_reduced, s11407)
--     transported back through injectivity of mat  (lift_ne_one)
-- injectivity of ψ is the same ne-one fact via injective_iff_map_eq_one.
theorem free_so3_embedding :
    ∃ ψ : FreeGroup (Fin 2) →* (E ≃ₗᵢ[ℝ] E),
      Function.Injective ψ ∧
      (∀ w : FreeGroup (Fin 2), w ≠ 1 →
        LinearMap.det ((ψ w).toLinearEquiv.toLinearMap) = 1 ∧
        ψ w ≠ LinearIsometryEquiv.refl ℝ E)  := by
  obtain ⟨g, mat, hmatinj, hmatdet, hg0, hg0inv, hg1, hg1inv⟩ := so3_realization_hom
  have hdetA : (mat (g 0)).det = 1 := by rw [hg0]; exact gen_a_det_one
  have hdetB : (mat (g 1)).det = 1 := by rw [hg1]; exact gen_b_det_one
  have hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then mat (g 0) else (mat (g 0))⁻¹)
                    else (if x.2 then mat (g 1) else (mat (g 1))⁻¹))).prod ≠ 1 := by
    intro w hw
    simp only [hg0inv, hg1inv]
    simp only [hg0, hg1]
    exact rotation_word_ne_one_of_reduced _ _ _ _ rfl rfl rfl rfl w hw
  refine ⟨FreeGroup.lift g, ?_, ?_⟩
  · rw [injective_iff_map_eq_one]
    intro w hw
    by_contra hne
    exact lift_ne_one g mat (mat (g 0)) (mat (g 0))⁻¹ (mat (g 1)) (mat (g 1))⁻¹
      hmatinj rfl rfl rfl rfl hword w hne hw
  · intro w hw
    refine ⟨lift_det_one g mat hmatdet hdetA hdetB w, ?_⟩
    have h := lift_ne_one g mat (mat (g 0)) (mat (g 0))⁻¹ (mat (g 1)) (mat (g 1))⁻¹
      hmatinj rfl rfl rfl rfl hword w hw
    intro hc; exact h (by rw [hc]; rfl)

-- Build φ as the LINEAR embedding ψ : F₂ →* (E ≃ₗᵢ[ℝ] E) post-composed with the
-- coercion homomorphism (·).toIsometryEquiv : (E ≃ₗᵢ[ℝ] E) →* (E ≃ᵢ E).
-- Sub-goal `free_so3_embedding` supplies ψ with: injectivity, and (per nontrivial word)
-- det = 1 and ψ w ≠ refl — the genuine SO(3) freeness/rotation content.
-- The remaining work is pure packaging: the coercion is an injective monoid hom
-- (so φ is injective), every ψ w is linear (so φ w fixes 0), and φ w x = x ⇔ ψ w x = x,
-- whence rotation_fixed_set_on_sphere_finite (proved sibling) gives the finite fixed set.
theorem exists_free_isometry_embedding :
    ∃ φ : FreeGroup (Fin 2) →* (E ≃ᵢ E),
      Function.Injective φ ∧
      (∀ w : FreeGroup (Fin 2), φ w 0 = 0) ∧
      (∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite)  := by
  obtain ⟨ψ, hinj, hprop⟩ := free_so3_embedding
  let c : (E ≃ₗᵢ[ℝ] E) →* (E ≃ᵢ E) :=
    { toFun := fun g => g.toIsometryEquiv
      map_one' := rfl
      map_mul' := fun a b => rfl }
  have hcinj : Function.Injective c := fun x y hxy =>
    LinearIsometryEquiv.toIsometryEquiv_injective hxy
  refine ⟨c.comp ψ, ?_, ?_, ?_⟩
  · exact hcinj.comp hinj
  · intro w
    change (ψ w).toIsometryEquiv 0 = 0
    simp
  · intro w hw
    obtain ⟨hdet, hne⟩ := hprop w hw
    have hfin := rotation_fixed_set_on_sphere_finite (ψ w) hdet hne
    convert hfin using 2

-- Construct the z-rotation isometry family by realizing each orthogonal block matrix.
-- `hreal`: each M θ is orthogonal (z_rotation_block_orthogonal) so PROVED
-- orthogonal_matrix_isometry_equiv gives an `e : E ≃ᵢ E` acting as `toEuclideanLin (M θ)`;
-- `choose` extracts the family R. Origin clause: linear maps fix 0 (`simp`). Realization
-- clause (3) is `hR` verbatim. Power law: IsometryEquiv `ext`, then
-- `isometry_pow_realizes_matrix_pow` reduces `(R θ)^n x` to `toEuclideanLin (M θ ^ n) x`,
-- and `z_rotation_matrix_pow` collapses `M θ ^ n = M (n·θ)`. Three sub-goals: the matrix
-- power law (pure matrix induction), the isometry-power/matrix-power bridge (group induction),
-- and per-θ orthogonality of the block (pure entry computation).
theorem z_rotation_isometry_family_realizes_matrix :
    ∃ R : ℝ → (E ≃ᵢ E),
      (∀ θ : ℝ, R θ 0 = 0) ∧
      (∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ)) ∧
      (∀ (θ : ℝ) (x : E),
        R θ x =
          Matrix.toEuclideanLin
            (!![Real.cos θ, -Real.sin θ, 0;
                Real.sin θ,  Real.cos θ, 0;
                0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) x)  := by
  have hreal : ∀ θ : ℝ, ∃ e : E ≃ᵢ E, ∀ x : E,
      e x = Matrix.toEuclideanLin
        (!![Real.cos θ, -Real.sin θ, 0;
            Real.sin θ,  Real.cos θ, 0;
            0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) x :=
    fun θ => orthogonal_matrix_isometry_equiv _ (z_rotation_block_orthogonal θ)
  choose R hR using hreal
  refine ⟨R, fun θ => ?_, fun θ n => ?_, fun θ x => hR θ x⟩
  · rw [hR θ 0]; simp
  · ext x
    rw [isometry_pow_realizes_matrix_pow (R θ) _ (hR θ) n x, z_rotation_matrix_pow θ n,
        hR ((n : ℝ) * θ) x]

-- entry_kind: Builder
theorem x_rot_fixes_first_coord
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) :
    ∀ (φ : ℝ), (Q φ p) 0 = p 0 := by aesop

-- entry_kind: Builder
theorem x_rot_second_coord
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) :
    ∀ (φ : ℝ), (Q φ p) 1 = Real.cos φ * p 1 - Real.sin φ * p 2 := by aesop

-- x-rotation fixes coord 0 (=p 0) and sends coord 1 to cos φ·p₁ − sin φ·p₂; reduce the
-- two-clause collision set to the second-coord zero set, then case-split on p 0.
-- Sub-goals: x_rot_fixes_first_coord, x_rot_second_coord (component formulas, Builder);
-- cos_sin_combo_zero_countable (zeros of a nonzero cos/sin combination are countable, Backward).
-- p 0 ≠ 0 ⟹ clause-0 fails ⟹ ∅; p 0 = 0 ⟹ (p₁,p₂)≠0 (from p≠0) ⟹ trig zero set, .mono.
theorem x_rotation_collision_countable
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x) :
    ∀ p : E, p ≠ 0 →
      {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}.Countable  := by
  intro p hp
  have hc0 : ∀ (φ : ℝ), (Q φ p) 0 = p 0 := x_rot_fixes_first_coord Q hQ p
  have hc1 : ∀ (φ : ℝ), (Q φ p) 1 = Real.cos φ * p 1 - Real.sin φ * p 2 :=
    x_rot_second_coord Q hQ p
  by_cases h0 : p 0 = 0
  · have hne : p 1 ≠ 0 ∨ p 2 ≠ 0 := by
      by_contra h
      rw [not_or, not_not, not_not] at h
      apply hp
      ext i
      fin_cases i
      · exact h0
      · exact h.1
      · exact h.2
    have hsub : {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}
        ⊆ {φ : ℝ | Real.cos φ * p 1 - Real.sin φ * p 2 = 0} := by
      intro φ hφ
      simp only [Set.mem_setOf_eq] at hφ ⊢
      rw [← hc1 φ]; exact hφ.2
    have hcount : {φ : ℝ | Real.cos φ * p 1 - Real.sin φ * p 2 = 0}.Countable :=
      cos_sin_combo_zero_countable (p 1) (p 2) hne
    exact hcount.mono hsub
  · have hempty : {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0} = ∅ := by
      ext φ
      simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false, not_and]
      intro hcc _
      apply h0
      rw [← hc0 φ]; exact hcc
    rw [hempty]; exact Set.countable_empty

-- Witness Q = rotation about the x-axis, realized from the orthogonal block
-- !![1,0,0; 0,cos φ,-sin φ; 0,sin φ,cos φ] via PROVED orthogonal_matrix_isometry_equiv.
-- Two sub-goals: (1) x_rotation_block_orthogonal — that block satisfies Mᵀ·M = 1
-- (Builder entry computation); (2) x_rotation_collision_countable — for the realized
-- family, every off-origin p has a countable z-axis-collision angle set (Backward:
-- (Q φ p) 0 = p 0 is φ-independent, so p 0 ≠ 0 ⟹ ∅; p 0 = 0 ⟹ (p 1,p 2) ≠ 0 and
-- cos φ·p 1 - sin φ·p 2 = 0 cuts a discrete set). `choose` extracts Q from the per-φ
-- realization; origin clause is `rw [hQ φ 0]; simp` (the realization is linear).
theorem zaxis_collision_angles_per_point_countable :
    ∃ Q : ℝ → (E ≃ᵢ E),
      (∀ φ : ℝ, Q φ 0 = 0) ∧
      (∀ p : E, p ≠ 0 →
        {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}.Countable)  := by
  have hreal : ∀ φ : ℝ, ∃ e : E ≃ᵢ E, ∀ x : E,
      e x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x :=
    fun φ => orthogonal_matrix_isometry_equiv _ (x_rotation_block_orthogonal φ)
  choose Q hQ using hreal
  exact ⟨Q, fun φ => by rw [hQ φ 0]; simp, x_rotation_collision_countable Q hQ⟩

-- zaxis_bad_angles_countable: countable union over countable D of per-point z-axis-collision sets
-- Forward rationale: Grep + Loogle confirmed missing — R1 keywords searched:
-- 'isometry moves countable set off axis', 'origin-fixing isometry off z-axis countable',
-- 'rotation avoids countable directions sphere' (0 reusable mathlib hits).
-- STRATEGY PIVOT: bundled existence deduped against goal 3414; ship the reusable building block
-- the off-axis-mover proof consumes: angles θ where SOME p ∈ D lands on the z-axis form a
-- countable union over countable D, hence countable. Off-axis sibling of bad_angles_countable /
-- scaled_collision_countable; NOT the existence claim, so no dedupe against 3414.
-- Per-point countability carried as hcol, mirroring good_angle_avoids_collisions.
-- entry_kind: Builder
theorem zaxis_bad_angles_countable (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, {θ : ℝ | (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable) :
    {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable := by
  have heq : {θ : ℝ | ∃ p ∈ D, ((R θ) p).ofLp 0 = 0 ∧ ((R θ) p).ofLp 1 = 0} =
      ⋃ p ∈ D, {θ : ℝ | ((R θ) p).ofLp 0 = 0 ∧ ((R θ) p).ofLp 1 = 0} := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_iUnion, exists_prop]
  rw [heq]
  exact hD.biUnion hcol

-- entry_kind: Builder
theorem r0_components
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (t : ℝ) (x : E) :
    (R0 t x) 0 = Real.cos t * x 0 - Real.sin t * x 1 ∧
    (R0 t x) 1 = Real.sin t * x 0 + Real.cos t * x 1 := by aesop

-- collision set {t | R0 t p = q} ⊆ cosine level set, via the 2×2 z-rotation system.
-- Two strictly simpler sub-goals: (1) `r0_components` unfolds the matrix action into
-- its first-two scalar component equations q₀ = c·p₀ - s·p₁, q₁ = s·p₀ + c·p₁ (matrix
-- algebra, no analysis); (2) `cos_pinned_by_components` solves that 2×2 linear system
-- for cos t = (p₀q₀+p₁q₁)/(p₀²+p₁²) given off-axis ¬(p₀=0∧p₁=0) (pure field algebra).
-- After `intro t ht` and rewriting ht : R0 t p = q into the components, `exact` combines.
theorem collision_forces_cos
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) (hp : ¬ (p 0 = 0 ∧ p 1 = 0)) (q : E) :
    {t : ℝ | R0 t p = q} ⊆
      {t : ℝ | Real.cos t = (p 0 * q 0 + p 1 * q 1) / (p 0 ^ 2 + p 1 ^ 2)}  := by
  intro t ht
  simp only [Set.mem_setOf_eq] at ht ⊢
  obtain ⟨hc0, hc1⟩ := r0_components R0 hreal t p
  rw [ht] at hc0 hc1
  exact cos_pinned_by_components (Real.cos t) (Real.sin t) (p 0) (p 1) (q 0) (q 1) hc0 hc1 hp

-- Off-axis collision set {t | R0 t p = q} is countable, via a cosine level set.
-- For off-axis p the rotation angle's cosine is pinned: R0 t p = q forces
-- cos t = (p₀q₀ + p₁q₁)/(p₀²+p₁²), a single fixed value (collision_forces_cos:
-- unfold the rotation matrix on components 0,1 and solve the 2×2 system).
-- A cosine level set {t | cos t = c} is countable (cos_level_set_countable:
-- cos is strictly monotone on each [kπ,(k+1)π], so ≤1 root per interval over a
-- countable cover). The collision set is a subset of it, so Set.Countable.mono
-- transports countability back. Both sub-goals are strictly simpler: one is pure
-- matrix algebra, the other a matrix-free analytic fact.
theorem zrot_offaxis_collision_set_countable
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) (hp : ¬ (p 0 = 0 ∧ p 1 = 0)) (q : E) :
    {t : ℝ | R0 t p = q}.Countable  := by
  have key := collision_forces_cos R0 hreal p hp q
  have hcos := cos_level_set_countable ((p 0 * q 0 + p 1 * q 1) / (p 0 ^ 2 + p 1 ^ 2))
  exact hcos.mono key

-- Reuse the proved z-rotation isometry family (origin-fixing + power law + matrix realization);
-- the only new content is the off-axis collision-countability clause.
-- z_rotation_isometry_family_realizes_matrix supplies R0 with clauses (1),(2) and the matrix
-- realization `hreal`; feed `hreal` into the single sub-goal zrot_offaxis_collision_set_countable
-- (for an off-axis p, the rotated xy-component traces a circle, so {t | R0 t p = q} is countable).
theorem zrotation_offaxis_collision_family :
    ∃ R0 : ℝ → (E ≃ᵢ E),
      (∀ t : ℝ, R0 t 0 = 0) ∧
      (∀ (t : ℝ) (n : ℕ), (R0 t) ^ n = R0 ((n : ℝ) * t)) ∧
      (∀ p : E, ¬ (p 0 = 0 ∧ p 1 = 0) → ∀ q : E, {t : ℝ | R0 t p = q}.Countable)  := by
  obtain ⟨R0, h0, hpow, hreal⟩ := z_rotation_isometry_family_realizes_matrix
  refine ⟨R0, h0, hpow, fun p hp q => ?_⟩
  exact zrot_offaxis_collision_set_countable R0 hreal p hp q

-- Direct leaf: conjugation transports the disjoint orbit.
-- (g⁻¹·ρ₀·g)^n = g⁻¹·ρ₀ⁿ·g (conj_pow), so its image of D is g⁻¹ '' (ρ₀ⁿ '' (g '' D));
-- disjointness then transfers across the injective map g⁻¹ via Set.disjoint_image_iff,
-- reducing each pair to the hypothesis h on the ρ₀-orbit of g '' D.
theorem conj_pairwise_transport (g rho0 : E ≃ᵢ E) (D : Set E)
    (h : Pairwise (fun i j : ℕ =>
      Disjoint ((rho0 ^ i) '' (g '' D)) ((rho0 ^ j) '' (g '' D)))) :
    Pairwise (fun i j : ℕ =>
      Disjoint (((g⁻¹ * rho0 * g) ^ i) '' D) (((g⁻¹ * rho0 * g) ^ j) '' D))  := by
  have key : ∀ n : ℕ, ((g⁻¹ * rho0 * g) ^ n) '' D = ⇑g⁻¹ '' ((rho0 ^ n) '' (g '' D)) := by
    intro n
    have hconj : (g⁻¹ * rho0 * g) ^ n = g⁻¹ * rho0 ^ n * g := by
      have : g⁻¹ * rho0 * g = g⁻¹ * rho0 * (g⁻¹)⁻¹ := by rw [inv_inv]
      rw [this, conj_pow, inv_inv]
    rw [hconj]
    simp [Set.image_image, mul_assoc]
  intro i j hij
  rw [key i, key j]
  exact (Set.disjoint_image_iff g⁻¹.injective).mpr (h hij)

-- Direct: `wlog i < j` (Disjoint is symmetric), set n = j - i ≥ 1, then
-- (g^j) '' D = (g^i) '' ((g^n) '' D) via pow_add + image_comp; cancel the injective g^i
-- (Set.disjoint_image_iff) to land on `(h n).symm : Disjoint D ((g^n) '' D)`.
theorem pairwise_disjoint_of_shift_disjoint (g : E ≃ᵢ E) (D : Set E)
    (h : ∀ n : ℕ, 1 ≤ n → Disjoint ((g ^ n) '' D) D) :
    Pairwise (fun i j : ℕ => Disjoint ((g ^ i) '' D) ((g ^ j) '' D))  := by
  intro i j hij
  wlog hlt : i < j generalizing i j
  · have hji : j < i := (not_lt.mp hlt).lt_of_ne (Ne.symm hij)
    exact (this (Ne.symm hij) hji).symm
  set n := j - i with hn
  have hjn : j = i + n := by omega
  have h1n : 1 ≤ n := by omega
  have hcomp : (g ^ j) '' D = (g ^ i) '' ((g ^ n) '' D) := by
    rw [hjn, pow_add, ← Set.image_comp]
    rfl
  rw [hcomp, Set.disjoint_image_iff (g ^ i).injective]
  exact (h n h1n).symm

-- entry_kind: Builder
-- scaled_collision_countable: preimage of collision set under θ ↦ n·θ is countable
-- because it equals the image of {φ | R φ p = q} under φ ↦ φ/(n:ℝ), inheriting countability.
theorem scaled_collision_countable (D : Set E) (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    ∀ (n : ℕ), 1 ≤ n → ∀ p ∈ D, ∀ q ∈ D,
      {θ : ℝ | R ((n : ℝ) * θ) p = q}.Countable := by
  intro n hn p hp q hq
  have hn_pos : (n : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (by omega)
  have heq : {θ : ℝ | R ((n : ℝ) * θ) p = q} =
      (fun φ => φ / (n : ℝ)) '' {φ : ℝ | R φ p = q} := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_image]
    constructor
    · intro h
      exact ⟨(n : ℝ) * θ, h, by field_simp⟩
    · rintro ⟨φ, hφ, rfl⟩
      rwa [mul_div_cancel₀ φ hn_pos]
  rw [heq]
  exact (hcol p hp q hq).image _

-- Bad-angle set = ⋃ over n the per-n fiber; split the union over ℕ (Countable).
-- For n=0 the fiber is empty (1 ≤ n fails); for n ≥ 1 it is the D×D-biUnion of
-- the scaled collision sets {θ | R(nθ)p=q}, each countable by sub-goal
-- [scaled_collision_countable] (preimage of hcol's set under θ ↦ nθ, n ≠ 0).
theorem bad_angles_countable (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}.Countable  := by
  have hscaled := scaled_collision_countable D R hcol

  have key : {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}
      = ⋃ (n : ℕ), {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} := by
    ext θ; simp only [Set.mem_setOf_eq, Set.mem_iUnion]
  rw [key]
  apply Set.countable_iUnion
  intro n
  by_cases hn : 1 ≤ n
  · have : {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}
        = ⋃ p ∈ D, ⋃ q ∈ D, {θ : ℝ | R ((n : ℝ) * θ) p = q} := by
      ext θ; simp only [Set.mem_setOf_eq, Set.mem_iUnion, hn, true_and]; tauto
    rw [this]
    exact hD.biUnion (fun p hp => hD.biUnion (fun q hq => hscaled n hn p hp q hq))

  · have : {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} = ∅ := by
      ext θ; simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false, not_and]
      intro h; exact absurd h hn
    rw [this]; exact Set.countable_empty

-- Hilbert-hotel angle choice: ρ := R θ for a θ outside the countable "bad" set
-- B of angles causing a collision R(nθ)·p = q (n≥1, p,q ∈ D).
-- Sole sub-goal: B is countable [bad_angles_countable]. The "∃ θ ∉ B" step is
-- inlined (countable B ≠ univ since ℝ is uncountable) to dodge the dedupe-probe
-- leaf misfire. Combinator: take θ ∉ B, ρ := R θ; ρ0=0 by h0; disjointness is
-- exactly θ ∉ B via hpow.
theorem good_angle_avoids_collisions (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (h0 : ∀ θ : ℝ, R θ 0 = 0)
    (hpow : ∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧ ∀ n : ℕ, 1 ≤ n → Disjoint ((ρ ^ n) '' D) D  := by
  have hB : {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}.Countable :=
    bad_angles_countable D hD R hcol
  obtain ⟨θ, hθ⟩ : ∃ θ : ℝ,
      θ ∉ {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} := by
    by_contra h
    push_neg at h
    exact Cardinal.not_countable_real (by rwa [Set.eq_univ_of_forall h] at hB)
  refine ⟨R θ, h0 θ, ?_⟩
  intro n hn
  rw [Set.disjoint_left]
  rintro x ⟨p, hp, rfl⟩ hx
  exact hθ ⟨n, hn, p, hp, (R θ ^ n) p, hx, by rw [hpow]⟩

-- Hilbert-hotel z-axis angle choice (z-axis analogue of good_angle_avoids_collisions / s11432).
-- Sole brick: the "bad" set B = {θ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0} is countable
-- [proved sibling zaxis_bad_angles_countable]. The "∃ θ ∉ B" step is inlined (countable B ≠ univ
-- since ℝ is uncountable). Combinator: take θ ∉ B; for p ∈ D, landing on the z-axis would witness
-- membership in B, contradiction.
theorem good_angle_avoids_zaxis
    (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, {θ : ℝ | (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable) :
    ∃ θ : ℝ, ∀ p ∈ D, ¬ ((R θ p) 0 = 0 ∧ (R θ p) 1 = 0)  := by
  have hB : {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable :=
    zaxis_bad_angles_countable D hD R hcol
  obtain ⟨θ, hθ⟩ : ∃ θ : ℝ,
      θ ∉ {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0} := by
    by_contra h
    push_neg at h
    exact Cardinal.not_countable_real (by rwa [Set.eq_univ_of_forall h] at hB)
  refine ⟨θ, ?_⟩
  intro p hp hcontra
  exact hθ ⟨p, hp, hcontra.1, hcontra.2⟩

-- Hilbert-hotel disjoint-orbit existence (off-origin), THIN glue over proved bricks.
-- Two sub-goals: (1) zrotation_offaxis_collision_family — a z-rotation isometry family
-- R₀ fixing 0, with the power law, and countable collision-angle sets for every off-axis
-- point; (2) conj_pairwise_transport — transport a pairwise-disjoint orbit through the
-- single conjugation g⁻¹·ρ₀·g.  All the axis-selection and assembly is inline:
--   • get an origin-fixing isometry g moving every p ∈ D off the z-axis, by feeding
--     good_angle_avoids_zaxis the x-rotation family Q (zaxis_collision_angles_per_point_countable);
--     the p ≠ 0 side-condition comes from hD0 (this is where 0 ∉ D is load-bearing);
--   • R₀'s off-axis collision clause then holds on g '' D, so good_angle_avoids_collisions
--     yields a z-rotation ρ₀ with shift-disjoint orbit over g '' D, upgraded to Pairwise by
--     pairwise_disjoint_of_shift_disjoint;
--   • conjugating by g (conj_pairwise_transport) carries Pairwise back to ρ := g⁻¹·ρ₀·g over D,
--     and ρ 0 = 0 since g, ρ₀ both fix 0.
theorem exists_rotation_pairwise_disjoint_orbit_off_origin
    (D : Set E) (hD : D.Countable) (hD0 : (0 : E) ∉ D) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧
      Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))  := by
  obtain ⟨R₀, h0₀, hpow₀, hcol₀⟩ := zrotation_offaxis_collision_family
  obtain ⟨Q, hQ0, hQcol⟩ := zaxis_collision_angles_per_point_countable
  obtain ⟨φ, hφ⟩ := good_angle_avoids_zaxis D hD Q
    (fun p hp => hQcol p (by rintro rfl; exact hD0 hp))
  set g : E ≃ᵢ E := Q φ with hg
  have hg0 : g 0 = 0 := hQ0 φ
  have hgoff : ∀ p ∈ D, ¬ ((g p) 0 = 0 ∧ (g p) 1 = 0) := hφ
  have hcolR0 : ∀ p ∈ g '' D, ∀ q ∈ g '' D, {t : ℝ | R₀ t p = q}.Countable := by
    rintro p ⟨p₀, hp₀, rfl⟩ q _
    exact hcol₀ (g p₀) (hgoff p₀ hp₀) q
  obtain ⟨ρ₀, hρ₀0, hshift⟩ :=
    good_angle_avoids_collisions (g '' D) (hD.image g) R₀ h0₀ hpow₀ hcolR0
  have hpair : Pairwise (fun i j : ℕ =>
      Disjoint ((ρ₀ ^ i) '' (g '' D)) ((ρ₀ ^ j) '' (g '' D))) :=
    pairwise_disjoint_of_shift_disjoint ρ₀ (g '' D) hshift
  refine ⟨g⁻¹ * ρ₀ * g, ?_, conj_pairwise_transport g ρ₀ D hpair⟩
  have e1 : (g⁻¹ * ρ₀ * g) 0 = g⁻¹ (ρ₀ (g 0)) := rfl
  rw [e1, hg0, hρ₀0]
  exact (IsometryEquiv.symm_apply_eq g).mpr hg0.symm

-- half_sphere_two_distinct: two explicit antipodal points witness the radius-1/2 sphere is nonempty
-- Uses EuclideanSpace.single to build (1/2,0,0) and (-1/2,0,0); norm computed by simp,
-- distinctness by extracting the 0th coordinate and norm_num.
theorem half_sphere_two_distinct :
    ∃ p q : E, p ∈ Metric.sphere (0 : E) (1 / 2) ∧
      q ∈ Metric.sphere (0 : E) (1 / 2) ∧ p ≠ q := by
  refine ⟨EuclideanSpace.single (0 : Fin 3) (1/2 : ℝ),
          EuclideanSpace.single (0 : Fin 3) (-1/2 : ℝ), ?_, ?_, ?_⟩
  · simp
  · simp
  · intro h
    have h0 : (EuclideanSpace.single (0 : Fin 3) (1/2 : ℝ)).ofLp (0 : Fin 3) =
              (EuclideanSpace.single (0 : Fin 3) (-1/2 : ℝ)).ofLp (0 : Fin 3) :=
      congr_arg (fun x => x.ofLp 0) h
    simp at h0
    norm_num at h0

-- The radius-1/2 sphere in ℝ³ is uncountable: it is preconnected (dim > 1, via
-- `isConnected_sphere`) and contains two distinct points, and a preconnected set
-- with two distinct points in a metric space is uncountable.
-- Sub-goals: (1) general topology lemma `preconnected_two_points_uncountable`
-- (abstract, no sphere geometry); (2) `half_sphere_two_distinct` (two explicit
-- antipodal points on the radius-1/2 sphere). Preconnectedness is cited inline.
theorem half_sphere_uncountable : ¬ (Metric.sphere (0 : E) (1 / 2)).Countable  := by
  have hrank : (1 : Cardinal) < Module.rank ℝ E := by
    have h3 : Module.rank ℝ E = 3 := by
      rw [← Module.finrank_eq_rank]; simp [E]
    rw [h3]; norm_num
  have hpre : IsPreconnected (Metric.sphere (0 : E) (1 / 2)) :=
    (isConnected_sphere hrank 0 (by norm_num)).isPreconnected
  obtain ⟨p, q, hp, hq, hpq⟩ := half_sphere_two_distinct
  exact preconnected_two_points_uncountable hpre hp hq hpq

-- entry_kind: Builder
-- fixed_union_countable: countable union of finite fixed-point sets via Set.countable_iUnion
theorem fixed_union_countable (R : E ≃ₗᵢ[ℝ] E)
    (hfin : ∀ n : ℕ, 1 ≤ n → {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ n) x = x}.Finite) :
    (⋃ n : ℕ, {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ (n + 1)) x = x}).Countable := by
  apply Set.countable_iUnion
  intro n
  exact (hfin (n + 1) (Nat.succ_pos n)).countable

-- The radius-1/2 fixed set is the image of the radius-1 fixed set under x ↦ (1/2)•x.
-- Scale half→full by x ↦ 2•x: it injects the half-sphere fixed set into the radius-1
-- fixed set (proved finite as rotation_fixed_set_on_sphere_finite), so finiteness pulls back.
theorem fixed_set_half_sphere_finite : ∀ (R : E ≃ₗᵢ[ℝ] E),
    LinearMap.det (R.toLinearEquiv.toLinearMap) = 1 → R ≠ LinearIsometryEquiv.refl ℝ E →
    {x ∈ Metric.sphere (0 : E) (1 / 2) | R x = x}.Finite  := by
  intro R hdet hT
  have hfull := rotation_fixed_set_on_sphere_finite R hdet hT
  apply Set.Finite.of_finite_image (f := fun x => (2 : ℝ) • x)
  · apply hfull.subset
    rintro y ⟨x, ⟨hx_sph, hx_fix⟩, rfl⟩
    simp only [Set.mem_setOf_eq, Metric.mem_sphere, dist_eq_norm, sub_zero] at hx_sph ⊢
    refine ⟨?_, ?_⟩
    · rw [norm_smul, Real.norm_eq_abs, hx_sph]; norm_num
    · rw [map_smul, hx_fix]
  · intro a _ b _ hab
    exact smul_right_injective E (by norm_num) hab

-- Uncountable-sphere escape: the union over n of the n+1-power fixed sets on the
-- radius-1/2 sphere is countable (fixed_union_countable: each finite ⇒ countable union),
-- so the uncountable sphere is not contained in it; pick c in the sphere outside the union.
-- That c has ‖c‖ = 1/2 ≤ 1/2, and any positive power fixing c would place c (= R^(m+1) c)
-- back into the union, contradicting the choice. The lone sub-goal is the countability fact.
theorem exists_not_fixed_in_uncountable_sphere : ∀ (R : E ≃ₗᵢ[ℝ] E),
    ¬ (Metric.sphere (0 : E) (1 / 2)).Countable →
    (∀ n : ℕ, 1 ≤ n → {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ n) x = x}.Finite) →
    ∃ c, ‖c‖ ≤ 1 / 2 ∧ ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c  := by
  intro R hunc hfin
  have hBc : (⋃ n : ℕ, {x ∈ Metric.sphere (0:E) (1/2) | (R ^ (n+1)) x = x}).Countable :=
    fixed_union_countable R hfin
  have hns : ¬ (Metric.sphere (0:E) (1/2)) ⊆
      (⋃ n : ℕ, {x ∈ Metric.sphere (0:E) (1/2) | (R ^ (n+1)) x = x}) :=
    fun h => hunc (hBc.mono h)
  rw [Set.not_subset] at hns
  obtain ⟨c, hcs, hcB⟩ := hns
  have hnorm : ‖c‖ = 1/2 := mem_sphere_zero_iff_norm.mp hcs
  refine ⟨c, le_of_eq hnorm, ?_⟩
  intro n hn heq
  apply hcB
  obtain ⟨m, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (by omega : n ≠ 0)
  exact Set.mem_iUnion.mpr ⟨m, hcs, heq⟩

-- Take R := ψ (of 0), a single free generator of the proved SO(3) embedding ψ
-- (free_so3_embedding): an infinite-order det-1 rotation. For each n ≥ 1, R^n = ψ((of 0)^n)
-- with (of 0)^n ≠ 1, so R^n is a non-trivial det-1 isometry whose fixed set on the radius-1/2
-- sphere is finite (fixed_set_half_sphere_finite bridges rotation_fixed_set_on_sphere_finite
-- to radius 1/2). The union over n ≥ 1 of these fixed sets is countable, but the sphere is
-- uncountable (half_sphere_uncountable), so a point c with ‖c‖ = 1/2 escapes every power
-- (exists_not_fixed_in_uncountable_sphere). Sub-goals: of_pow_ne_one (generator has infinite
-- order), the radius-1/2 finiteness bridge, sphere uncountability, and the set-theoretic
-- "uncountable minus countably-many finite sets is nonempty" combine.
theorem exists_small_irrational_rotation :
    ∃ (R : E ≃ₗᵢ[ℝ] E) (c : E),
      ‖c‖ ≤ 1 / 2 ∧ ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c  := by
  obtain ⟨ψ, hinj, hprop⟩ := free_so3_embedding
  have hfin : ∀ n : ℕ, 1 ≤ n →
      {x ∈ Metric.sphere (0 : E) (1 / 2) | ((ψ (FreeGroup.of 0)) ^ n) x = x}.Finite := by
    intro n hn
    rw [(map_pow ψ (FreeGroup.of 0) n).symm]
    obtain ⟨hdet, hne⟩ := hprop ((FreeGroup.of 0) ^ n) (of_pow_ne_one n hn)
    exact fixed_set_half_sphere_finite _ hdet hne
  exact ⟨ψ (FreeGroup.of 0),
    exists_not_fixed_in_uncountable_sphere (ψ (FreeGroup.of 0)) half_sphere_uncountable hfin⟩

-- Closed form for the origin-orbit of the conjugated rotation ρ x = R(x-c)+c.
-- Induction on n: base 0 is `c - c = 0`; the step rewrites ρ^(k+1) = ρ ∘ ρ^k,
-- applies the inductive hypothesis and the defining equation hρ, uses linearity
-- of R (map_sub) and R^(k+1) = R ∘ R^k, then closes by abelian-group algebra.
set_option maxHeartbeats 0 in
-- the (ρ^n : E ≃ᵢ E) application on EuclideanSpace ℝ (Fin 3) blows past the
-- default 200k heartbeat whnf limit; lift it.
theorem conjugate_orbit_formula (ρ : E ≃ᵢ E) (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hρ : ∀ x : E, ρ x = R (x - c) + c) :
    ∀ n : ℕ, (ρ ^ n) 0 = c - (R ^ n) c  := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    rw [pow_succ', IsometryEquiv.coe_mul, Function.comp_apply, ih, hρ,
      pow_succ', LinearIsometryEquiv.coe_mul, Function.comp_apply]
    simp
    abel

-- entry_kind: Builder
theorem conjugate_orbit_ne_zero (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hfix : ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c) (n : ℕ) (hn : 1 ≤ n) :
    c - (R ^ n) c ≠ 0 := by exact sub_ne_zero_of_ne fun a ↦ hfix n hn (id (Eq.symm a))

-- entry_kind: Builder
-- conjugate_orbit_norm_bound: ‖c - Rⁿc‖ ≤ 2‖c‖ ≤ 1 via triangle ineq + isometry norm
theorem conjugate_orbit_norm_bound (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hc : ‖c‖ ≤ 1 / 2) (n : ℕ) :
    ‖c - (R ^ n) c‖ ≤ 1 := by
  calc ‖c - (R ^ n) c‖
      ≤ ‖c‖ + ‖(R ^ n) c‖ := norm_sub_le _ _
    _ = ‖c‖ + ‖c‖ := by rw [(R ^ n).norm_map]
    _ ≤ 1 := by linarith

-- Conjugate the linear isometry `R` by the translation `x ↦ x - c`.
-- Build the `IsometryEquiv` explicitly: `toFun x = R (x - c) + c`, inverse
-- `y ↦ R.symm (y - c) + c`; the two `left/right_inv` close by `simp`, and the
-- isometry law reduces to `R`'s isometry plus translation-invariance of `edist`
-- (`edist_add_right`/`edist_sub_right`). The pointwise formula then holds by `rfl`.
-- Direct leaf — no sub-goals.
theorem exists_conjugated_isometry (R : E ≃ₗᵢ[ℝ] E) (c : E) :
    ∃ ρ : E ≃ᵢ E, ∀ x : E, ρ x = R (x - c) + c  := by
  refine ⟨⟨⟨fun x => R (x - c) + c, fun y => R.symm (y - c) + c, ?_, ?_⟩, ?_⟩, fun x => rfl⟩
  · intro x; simp
  · intro y; simp
  · intro x y
    change edist (R (x - c) + c) (R (y - c) + c) = edist x y
    rw [edist_add_right, R.isometry (x - c) (y - c), edist_sub_right]

-- Conjugate a small-vector linear rotation `R` by the translation `x ↦ x - c`:
-- `ρ x = R (x - c) + c` is an isometry whose origin-orbit satisfies `(ρ ^ n) 0 = c - R ^ n c`.
-- Sub-goals: (1) build the conjugated isometry with that pointwise formula;
-- (2) the closed-form orbit by induction; (3) the orbit lies in the unit ball
-- (`‖c - R ^ n c‖ ≤ 2‖c‖ ≤ 1`); (4) it never returns to `0` for `n ≥ 1` (from `hfix`).
theorem conjugate_origin_orbit (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hc : ‖c‖ ≤ 1 / 2) (hfix : ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c) :
    ∃ ρ : E ≃ᵢ E,
      (∀ n : ℕ, (ρ ^ n) 0 ∈ Metric.closedBall (0 : E) 1) ∧
      (∀ n : ℕ, 1 ≤ n → (ρ ^ n) 0 ≠ 0)  := by
  obtain ⟨ρ, hρ⟩ := exists_conjugated_isometry R c
  have horbit := conjugate_orbit_formula ρ R c hρ
  refine ⟨ρ, ?_, ?_⟩
  · intro n
    rw [Metric.mem_closedBall, dist_zero_right, horbit n]
    exact conjugate_orbit_norm_bound R c hc n
  · intro n hn
    rw [horbit n]
    exact conjugate_orbit_ne_zero R c hfix n hn

-- Absorb {0} via an off-origin rotation: ρ conjugates a linear rotation R by a
-- translation that moves the rotation axis off the origin, so the 0-orbit traces a
-- circle of radius ‖c‖ ≤ 1/2 through the origin.
-- (1) exists_small_irrational_rotation: a linear rotation R and a small vector c
--     (‖c‖ ≤ 1/2) such that no positive power of R fixes c (irrational angle).
-- (2) conjugate_origin_orbit: build ρ x = R(x - c) + c; then (ρ^n) 0 = c - R^n c,
--     so ‖(ρ^n) 0‖ ≤ ‖c‖ + ‖R^n c‖ = 2‖c‖ ≤ 1 (in the ball) and (ρ^n) 0 = 0 ↔
--     R^n c = c, excluded for n ≥ 1 by hfix.
theorem exists_bounded_injective_origin_orbit :
    ∃ ρ : E ≃ᵢ E,
      (∀ n : ℕ, (ρ ^ n) 0 ∈ Metric.closedBall (0 : E) 1) ∧
      (∀ n : ℕ, 1 ≤ n → (ρ ^ n) 0 ≠ 0)  := by
  obtain ⟨R, c, hc, hfix⟩ := exists_small_irrational_rotation
  exact conjugate_origin_orbit R c hc hfix

-- Absorb {0} via an off-origin isometry ρ whose 0-orbit stays in the ball and never
-- returns to 0.  Reduce the Set-level claim to a pointwise existence:
-- exists_bounded_injective_origin_orbit gives ρ with `(ρ^n) 0 ∈ ball` (⊆-part, after
-- `image_singleton` + `iUnion_subset`) and `(ρ^n) 0 ≠ 0` for n≥1 (the shift-disjointness
-- `Disjoint ((ρ^n)''{0}) {0}`), fed through the proved pairwise_disjoint_of_shift_disjoint
-- (s11430) to upgrade single shifts to the full ℕ-indexed Pairwise family.
theorem bounded_injective_rotation_orbit :
    ∃ ρ : E ≃ᵢ E,
      (⋃ n : ℕ, (ρ ^ n) '' ({0} : Set E)) ⊆ Metric.closedBall (0 : E) 1 ∧
      Pairwise (fun i j : ℕ =>
        Disjoint ((ρ ^ i) '' ({0} : Set E)) ((ρ ^ j) '' ({0} : Set E)))  := by
  have h_orbit := exists_bounded_injective_origin_orbit
  obtain ⟨ρ, hball, hne⟩ := h_orbit
  refine ⟨ρ, ?_, ?_⟩
  · apply Set.iUnion_subset
    intro n
    rw [Set.image_singleton]
    intro x hx
    rw [Set.mem_singleton_iff] at hx
    subst hx
    exact hball n
  · apply pairwise_disjoint_of_shift_disjoint ρ ({0} : Set E)
    intro n hn
    rw [Set.image_singleton]
    rw [Set.disjoint_singleton]
    exact hne n hn

-- entry_kind: Builder
-- transfer_disjoint: preimage preserves disjointness; intersecting with h.source gives the result
theorem transfer_disjoint (h f g : Equidecomp E (E ≃ᵢ E))
    (hdisj : Disjoint f.source g.source) :
    Disjoint (h.source ∩ h ⁻¹' f.source) (h.source ∩ h ⁻¹' g.source) := by
  exact (hdisj.preimage h).mono Set.inter_subset_right Set.inter_subset_right

-- entry_kind: Builder
-- transfer_source: PartialEquiv.trans_source algebra — sandwich source = h.source ∩ h⁻¹'p.source
-- Unfolds Equidecomp.trans/symm to PartialEquiv, applies trans_source twice and symm_source,
-- then uses p.map_source' to discharge the extra p.target membership in the mpr direction.
theorem transfer_source (h p : Equidecomp E (E ≃ᵢ E)) (hpt : p.target = h.target) :
    (h.trans (p.trans h.symm)).source = h.source ∩ h ⁻¹' p.source := by
  simp only [Equidecomp.trans_toPartialEquiv, Equidecomp.symm_toPartialEquiv,
             PartialEquiv.trans_source, PartialEquiv.symm_source, ← hpt]
  ext x
  simp only [Set.mem_inter_iff, Set.mem_preimage]
  constructor
  · rintro ⟨hx_src, hx_h, _⟩
    exact ⟨hx_src, hx_h⟩
  · rintro ⟨hx_src, hx_h⟩
    exact ⟨hx_src, hx_h, p.map_source' hx_h⟩

-- entry_kind: Builder
-- transfer_union: set-algebra close: distribute ∩ over ∪, preimage_union, hunion, map_source'
theorem transfer_union (A B : Set E) (h f g : Equidecomp E (E ≃ᵢ E))
    (hsrc : h.source = A) (htgt : h.target = B) (hunion : f.source ∪ g.source = B) :
    (h.source ∩ h ⁻¹' f.source) ∪ (h.source ∩ h ⁻¹' g.source) = A := by
  rw [← Set.inter_union_distrib_left, ← Set.preimage_union, hunion, ← htgt]
  ext x
  simp only [Set.mem_inter_iff, Set.mem_preimage]
  constructor
  · rintro ⟨hx, _⟩; rwa [hsrc] at hx
  · intro hx
    rw [← hsrc] at hx
    exact ⟨hx, h.map_source' hx⟩

-- entry_kind: Builder
theorem transfer_target_corrected (h p : Equidecomp E (E ≃ᵢ E))
    (hpt : p.target = h.target) (hps : p.source ⊆ h.target) :
    (h.trans (p.trans h.symm)).target = h.source := by aesop

-- entry_kind: Builder
-- is_decomp_hilbert: the piecewise map f (ρ on T, id elsewhere) witnesses Equidecomp.IsDecompOn
-- using witness set S = {ρ, 1} — each point in A is moved by ρ (if in T) or fixed by 1 (if not)
theorem is_decomp_hilbert (A T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S := by
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  refine ⟨{ρ, 1}, fun a _ => ?_⟩
  by_cases hT : a ∈ T
  · exact ⟨ρ, Finset.mem_insert_self ρ {1}, hf a hT⟩
  · exact ⟨1, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)),
      by rw [hf' a hT]; rfl⟩

-- entry_kind: Builder
-- left_inv_hilbert: g∘f = id on A; case-split on T membership using ρ''T = T\D ⊆ T
theorem left_inv_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f g : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (hshift : ρ '' T = T \ D) :
    ∀ x ∈ A, g (f x) = x := by
  intro x _
  by_cases hxT : x ∈ T
  · rw [hf x hxT]
    have hρxT : ρ x ∈ T := by
      have hmem : ρ x ∈ ρ '' T := Set.mem_image_of_mem _ hxT
      rw [hshift] at hmem
      exact hmem.1
    rw [hg (ρ x) hρxT]
    exact ρ.symm_apply_apply x
  · rw [hf' x hxT, hg' x hxT]

-- entry_kind: Builder
-- map_source_hilbert: abstract Hilbert-hotel piecewise map sends A into A \ D
-- Case x∈T: f x = ρ x ∈ ρ''T = T\D ⊆ A\D. Case x∉T: f x = x ∉ D (since D⊆T).
theorem map_source_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hDT : D ⊆ T) (hTA : T ⊆ A) (hshift : ρ '' T = T \ D) :
    ∀ x ∈ A, f x ∈ A \ D := by
  intro x hxA
  by_cases hxT : x ∈ T
  · rw [hf x hxT]
    have hmem : ρ x ∈ ρ '' T := Set.mem_image_of_mem _ hxT
    rw [hshift] at hmem
    exact ⟨hTA hmem.1, hmem.2⟩
  · rw [hf' x hxT]
    exact ⟨hxA, fun hxD => hxT (hDT hxD)⟩

-- entry_kind: Builder
-- map_target_hilbert: g (= ρ⁻¹ on T, id off T) maps A \ D into A.
-- Key: y ∈ T ∧ y ∉ D  →  y ∈ T \ D = ρ '' T  →  ρ.symm y ∈ T ⊆ A;
-- y ∉ T  →  g y = y ∈ A.
theorem map_target_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (g : E → E)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (_hDT : D ⊆ T) (hTA : T ⊆ A) (hshift : ρ '' T = T \ D) :
    ∀ y ∈ A \ D, g y ∈ A := by
  intro y ⟨hyA, hyD⟩
  by_cases hyT : y ∈ T
  · rw [hg y hyT]
    have hy_shift : y ∈ ρ '' T := by rw [hshift]; exact ⟨hyT, hyD⟩
    obtain ⟨z, hz, hρz⟩ := hy_shift
    rw [← hρz, IsometryEquiv.symm_apply_apply]
    exact hTA hz
  · rw [hg' y hyT]; exact hyA

-- entry_kind: Builder
-- right_inv_hilbert: Hilbert-hotel right inverse law: f∘g = id on A\D,
-- using hshift (ρ''T = T\D) to show y∈T→ρ.symm y∈T, then f(ρ.symm y)=ρ(ρ.symm y)=y.
theorem right_inv_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f g : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (hshift : ρ '' T = T \ D) :
    ∀ y ∈ A \ D, f (g y) = y := by
  intro y hy
  simp only [Set.mem_diff] at hy
  obtain ⟨_, hyD⟩ := hy
  by_cases hyT : y ∈ T
  · have hgyT : ρ.symm y ∈ T := by
      have hy_in : y ∈ ρ '' T := by rw [hshift]; exact ⟨hyT, hyD⟩
      obtain ⟨x, hxT, hρxy⟩ := hy_in
      rwa [← hρxy, IsometryEquiv.symm_apply_apply]
    rw [hg y hyT, hf (ρ.symm y) hgyT, IsometryEquiv.apply_symm_apply]
  · rw [hg' y hyT, hf' y hyT]

-- entry_kind: Builder
-- shift_image: pushing ρ through ⋃ₙ ρⁿ''D shifts the index by 1, via pow_add + mul_apply rfl
theorem shift_image (D : Set E) (ρ : E ≃ᵢ E) :
    ρ '' (⋃ n : ℕ, (ρ ^ n) '' D) = ⋃ n : ℕ, (ρ ^ (n+1)) '' D := by
  simp only [Set.image_iUnion]
  congr 1; ext n
  rw [Set.image_image]
  have : ρ ^ (n + 1) = ρ * ρ ^ n := by
    rw [show n + 1 = 1 + n from by omega, pow_add, pow_one]
  rw [this]; rfl

-- ρ''T = T∖D via direct set-extensionality (no decomposition needed; leaf-bypass).
-- LHS = ⋃ₙ ρⁿ⁺¹''D = the union missing its n=0 term. After `ext`/`simp [mem_iUnion,mem_diff]`:
--   ⊇ (backward): x∈ρⁿ''D∧x∉D ⇒ n≠0 (else x∈ρ⁰''D=D, contra hxD) ⇒ x∈ρ^(m+1)''D.
--   ⊆ (forward):  x∈ρⁿ⁺¹''D ⇒ trivially in the full union; x∉D since x∈ρ⁰''D=D would
--                 collide with x∈ρⁿ⁺¹''D under hdisj (0≠n+1).
theorem tail_eq (D : Set E) (ρ : E ≃ᵢ E)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    (⋃ n : ℕ, (ρ ^ (n+1)) '' D) = (⋃ n : ℕ, (ρ ^ n) '' D) \ D  := by
  have hD0 : (ρ ^ (0:ℕ)) '' D = D := by simp
  ext x
  simp only [Set.mem_iUnion, Set.mem_diff]
  constructor
  · rintro ⟨n, hn⟩
    refine ⟨⟨n+1, hn⟩, ?_⟩
    intro hxD
    have h0 : x ∈ (ρ ^ (0:ℕ)) '' D := by rw [hD0]; exact hxD
    exact (hdisj (by omega : (0:ℕ) ≠ n+1)).le_bot ⟨h0, hn⟩
  · rintro ⟨⟨n, hn⟩, hxD⟩
    cases n with
    | zero => rw [hD0] at hn; exact absurd hn hxD
    | succ m => exact ⟨m, hn⟩

-- ρ''T = T∖D for the hotel T = ⋃ₙ ρⁿ''D: push ρ through the union (shift), then
-- peel the n=0 term using pairwise-disjoint orbits.
-- h_shift: image of union + ρ∘ρⁿ = ρⁿ⁺¹ collapses ρ''T to the shifted union ⋃ₙ ρⁿ⁺¹''D
--   (pure set algebra, no disjointness).
-- h_tail: the shifted union is exactly T with the n=0 piece D removed; ⊇ is trivial,
--   ⊆ uses hdisj (every ρⁿ⁺¹''D is disjoint from ρ⁰''D = D). Combine by rewriting.
theorem hotel_shift (D : Set E) (ρ : E ≃ᵢ E)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    ρ '' (⋃ n : ℕ, (ρ ^ n) '' D) = (⋃ n : ℕ, (ρ ^ n) '' D) \ D  := by
  have h_shift := shift_image D ρ
  have h_tail := tail_eq D ρ hdisj
  rw [h_shift, h_tail]

-- Relaxed Hilbert-hotel: same construction as the invariant version (s11467), but
-- T ⊆ A is supplied directly (hTA) instead of derived from ∀x∈A, ρx∈A — letting an
-- off-origin ρ (which maps closedBall 0 1 outside A) absorb D = {0}.
-- f = ρ on T = ⋃ₙ ρⁿ''D / id off T, inverse g = ρ⁻¹ on T / id off T; the 4
-- PartialEquiv laws + IsDecompOn are the proved abstract bricks, glued by Equidecomp.mk.
theorem relaxed_hilbert_hotel (A D : Set E) (ρ : E ≃ᵢ E)
    (hDA : D ⊆ A)
    (hTA : (⋃ n : ℕ, (ρ ^ n) '' D) ⊆ A)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    ∃ h : Equidecomp E (E ≃ᵢ E), h.source = A ∧ h.target = A \ D  := by
  classical
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hTdef
  set f : E → E := fun x => if x ∈ T then ρ x else x with hfdef
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hgdef
  have hf : ∀ x, x ∈ T → f x = ρ x := fun x hx => by simp [hfdef, hx]
  have hf' : ∀ x, x ∉ T → f x = x := fun x hx => by simp [hfdef, hx]
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := fun y hy => by simp [hgdef, hy]
  have hg' : ∀ y, y ∉ T → g y = y := fun y hy => by simp [hgdef, hy]
  have hDT : D ⊆ T := by
    intro x hx
    rw [hTdef]; exact Set.mem_iUnion.mpr ⟨0, by simpa using hx⟩
  have hshift : ρ '' T = T \ D := by rw [hTdef]; exact hotel_shift D ρ hdisj
  have hms : ∀ x ∈ A, f x ∈ A \ D := map_source_hilbert A D T ρ f hf hf' hDT hTA hshift
  have hmt : ∀ y ∈ A \ D, g y ∈ A := map_target_hilbert A D T ρ g hg hg' hDT hTA hshift
  have hli : ∀ x ∈ A, g (f x) = x := left_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hri : ∀ y ∈ A \ D, f (g y) = y := right_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S := is_decomp_hilbert A T ρ f hf hf'
  exact ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) hdec, rfl, rfl⟩

set_option maxHeartbeats 1000000 in
-- ρ^n applied to EuclideanSpace ℝ (Fin 3) blows past the default whnf budget; raise it.
-- hotel_subset_sphere: the orbit tower ⋃ₙ (ρ^n)''D of an origin-fixing isometry ρ stays
-- on S². Each (ρ^n) fixes 0 (induction, hfix) and an origin-fixing isometry preserves
-- norms (hnorm), so for d ∈ D ⊆ S² we get ‖(ρ^n) d‖ = ‖d‖ = 1. Sorry-free leaf.
theorem hotel_subset_sphere (D : Set E) (ρ : E ≃ᵢ E) (hρ0 : ρ 0 = 0)
    (hDs : D ⊆ Metric.sphere (0 : E) 1) :
    (⋃ n : ℕ, (ρ ^ n) '' D) ⊆ Metric.sphere (0 : E) 1  := by
  have hnorm : ∀ (g : E ≃ᵢ E), g 0 = 0 → ∀ z, ‖g z‖ = ‖z‖ := by
    intro g hg z
    calc ‖g z‖ = dist (g z) 0 := (dist_zero_right _).symm
      _ = dist (g z) (g 0) := by rw [hg]
      _ = dist z 0 := g.isometry.dist_eq z 0
      _ = ‖z‖ := dist_zero_right _
  have hfix : ∀ n : ℕ, (ρ ^ n) 0 = 0 := by
    intro n
    induction n with
    | zero => simp
    | succ k ih => rw [pow_succ]; change (ρ ^ k) (ρ 0) = 0; rw [hρ0, ih]
  intro x hx
  simp only [Set.mem_iUnion, Set.mem_image] at hx
  obtain ⟨n, d, hd, rfl⟩ := hx
  rw [Metric.mem_sphere, dist_zero_right, hnorm (ρ ^ n) (hfix n) d]
  have := hDs hd
  rw [Metric.mem_sphere, dist_zero_right] at this
  exact this

-- entry_kind: Builder
-- is_decomp_hilbert_origin_fixing: piecewise map f (ρ on T, id elsewhere) witnesses
-- Equidecomp.IsDecompOn with witness set {ρ, 1}, both of which fix the origin.
theorem is_decomp_hilbert_origin_fixing (A T : Set E) (ρ : E ≃ᵢ E) (hρ0 : ρ 0 = 0) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S ∧ ∀ s ∈ S, s 0 = 0 := by
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  refine ⟨{ρ, 1}, ?_, ?_⟩
  · intro a _
    by_cases hT : a ∈ T
    · exact ⟨ρ, Finset.mem_insert_self ρ {1}, hf a hT⟩
    · exact ⟨1, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)),
        by rw [hf' a hT]; rfl⟩
  · intro s hs
    simp only [Finset.mem_insert, Finset.mem_singleton] at hs
    rcases hs with rfl | rfl
    · exact hρ0
    · rfl

-- entry_kind: Builder
theorem is_decomp_hilbert_origin_fixing_2 (A T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) (hρ0 : ρ 0 = 0) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S ∧ ∀ s ∈ S, s 0 = 0 := by apply is_decomp_hilbert_origin_fixing <;> assumption

-- Compose two origin-fixing decompositions through `Equidecomp.trans`.
-- Witness finset is the pointwise product `S₂ ⋆ S₁` (`Finset.image₂ (·*·)`): on the
-- trans-source, `e₁` acts as some `g₁ ∈ S₁` and `e₂` (at `e₁ a`) as some `g₂ ∈ S₂`, so
-- the composite acts as `(g₂*g₁)•a` by `mul_smul`; each product fixes 0 since
-- `(g₂*g₁) 0 = g₂ (g₁ 0) = g₂ 0 = 0`. Direct leaf — no sub-goals.
theorem decomp_trans_origin_fixing
    (e₁ e₂ : Equidecomp E (E ≃ᵢ E)) (S₁ S₂ : Finset (E ≃ᵢ E))
    (hd₁ : Equidecomp.IsDecompOn e₁.toFun e₁.source S₁)
    (hd₂ : Equidecomp.IsDecompOn e₂.toFun e₂.source S₂)
    (h0₁ : ∀ s ∈ S₁, s 0 = 0) (h0₂ : ∀ s ∈ S₂, s 0 = 0) :
    ∃ S : Finset (E ≃ᵢ E),
      Equidecomp.IsDecompOn (e₁.trans e₂).toFun (e₁.trans e₂).source S ∧
      (∀ s ∈ S, s 0 = 0)  := by
  classical
  refine ⟨Finset.image₂ (· * ·) S₂ S₁, ?_, ?_⟩
  · intro a ha
    rw [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source] at ha
    obtain ⟨ha1, ha2⟩ := ha
    obtain ⟨g₁, hg₁, hfa⟩ := hd₁ a ha1
    obtain ⟨g₂, hg₂, hfb⟩ := hd₂ (e₁.toFun a) ha2
    refine ⟨g₂ * g₁, Finset.mem_image₂_of_mem hg₂ hg₁, ?_⟩
    change e₂.toFun (e₁.toFun a) = (g₂ * g₁) • a
    rw [hfb, hfa, mul_smul]
  · intro s hs
    obtain ⟨g₂, hg₂, g₁, hg₁, rfl⟩ := Finset.mem_image₂.mp hs
    calc (g₂ * g₁) 0 = g₂ (g₁ 0) := rfl
      _ = g₂ 0 := by rw [h0₁ g₁ hg₁]
      _ = 0 := h0₂ g₂ hg₂

-- Paradox transfers along equidecomposability: A ≃ B (via h) and B paradoxical ⇒ A paradoxical.
-- Same sandwich construction as the prior strategy (q := h.trans (p.trans h.symm)), but applies
-- the FIX for the lone dead sub-goal transfer_target: it needs the extra hypothesis p.source ⊆
-- h.target, which holds here since each B-piece source lies in f.source ∪ g.source = B = h.target.
-- Cites the three proved siblings (transfer_source/disjoint/union) directly; the single new
-- sub-goal transfer_target_corrected is transfer_target re-stated with the missing hps premise.
theorem paradoxical_transfer_along_equidecomp
    (A B : Set E) (h : Equidecomp E (E ≃ᵢ E)) (hsrc : h.source = A) (htgt : h.target = B)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = B ∧ f.target = B ∧ g.target = B) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = A ∧ f.target = A ∧ g.target = A  := by
  obtain ⟨f, g, hdisj, hunion, hftgt, hgtgt⟩ := hp
  have hft : f.target = h.target := hftgt.trans htgt.symm
  have hgt : g.target = h.target := hgtgt.trans htgt.symm
  have hfs : f.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_left
  have hgs : g.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_right
  refine ⟨h.trans (f.trans h.symm), h.trans (g.trans h.symm), ?_, ?_, ?_, ?_⟩
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_disjoint h f g hdisj
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_union A B h f g hsrc htgt hunion
  · rw [transfer_target_corrected h f hft hfs]; exact hsrc
  · rw [transfer_target_corrected h g hgt hgs]; exact hsrc

-- Mirror the proved non-origin-fixing transfer s11468 (q := h.trans (f.trans h.symm)), reusing
-- transfer_source/disjoint/union/target_corrected for the source/target/disjoint/union parts.
-- New content is the origin-fixing decomp data: decomp_trans_origin_fixing composes two
-- origin-fixing IsDecompOn finsets into one for an Equidecomp.trans; apply it twice
-- (f.trans h.symm, then h.trans …) to get Sf'/Sg' fixing 0 (each factor is a product of fixers).
theorem paradoxical_transfer_along_equidecomp_origin_fixing
    (A B : Set E) (h : Equidecomp E (E ≃ᵢ E)) (Sh Sh' : Finset (E ≃ᵢ E))
    (hsrc : h.source = A) (htgt : h.target = B)
    (hdec_h : Equidecomp.IsDecompOn h.toFun h.source Sh)
    (hdec_h' : Equidecomp.IsDecompOn h.symm.toFun h.symm.source Sh')
    (h0h : ∀ s ∈ Sh, s 0 = 0) (h0h' : ∀ s ∈ Sh', s 0 = 0)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = B ∧
        f.target = B ∧ g.target = B ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = A ∧
      f.target = A ∧ g.target = A ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨f, g, Sf, Sg, hdisj, hunion, hftgt, hgtgt, hdec_f, hdec_g, h0f, h0g⟩ := hp
  have hft : f.target = h.target := hftgt.trans htgt.symm
  have hgt : g.target = h.target := hgtgt.trans htgt.symm
  have hfs : f.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_left
  have hgs : g.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_right
  obtain ⟨Sfh, hdec_fh, h0fh⟩ :=
    decomp_trans_origin_fixing f h.symm Sf Sh' hdec_f hdec_h' h0f h0h'
  obtain ⟨Sf', hdec_f', h0f'⟩ :=
    decomp_trans_origin_fixing h (f.trans h.symm) Sh Sfh hdec_h hdec_fh h0h h0fh
  obtain ⟨Sgh, hdec_gh, h0gh⟩ :=
    decomp_trans_origin_fixing g h.symm Sg Sh' hdec_g hdec_h' h0g h0h'
  obtain ⟨Sg', hdec_g', h0g'⟩ :=
    decomp_trans_origin_fixing h (g.trans h.symm) Sh Sgh hdec_h hdec_gh h0h h0gh
  refine ⟨h.trans (f.trans h.symm), h.trans (g.trans h.symm), Sf', Sg',
    ?_, ?_, ?_, ?_, hdec_f', hdec_g', h0f', h0g'⟩
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_disjoint h f g hdisj
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_union A B h f g hsrc htgt hunion
  · rw [transfer_target_corrected h f hft hfs]; exact hsrc
  · rw [transfer_target_corrected h g hgt hgs]; exact hsrc

-- free_action_word_unique: freeness of φ forces a = b when φ a • y = φ b • y (y ∈ M)
-- Apply hfree to a⁻¹ * b: φ(a⁻¹*b)•y = (φa)⁻¹•(φb•y) = (φa)⁻¹•(φa•y) = y forces a⁻¹*b=1.
-- entry_kind: Builder

theorem free_action_word_unique
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (y : E) (hy : y ∈ M) (a b : FreeGroup (Fin 2)) (h : φ a • y = φ b • y) :
    a = b := by
  -- φ a • y = φ b • y implies φ(a⁻¹*b) • y = y, hence a⁻¹*b = 1 by freeness, so b = a
  have key : a⁻¹ * b = 1 := by
    by_contra hne
    exact hfree (a⁻¹ * b) hne y hy (by
      rw [map_mul, mul_smul, map_inv, ← h, inv_smul_smul])
  exact inv_mul_eq_one.mp key

-- Drop φ entirely: an orbit section exists for ANY group action.
-- `MulAction.compHom E φ` makes `FreeGroup (Fin 2)` act on `E` by `w • x = φ w • x`
-- (definitionally), so the abstract `orbit_section_general` (rep + word with
-- `wrd x • rep x = x` and `rep` constant on each orbit) specializes directly:
-- the two conjuncts close by `exact h1`/`exact h2` since compHom's `•` is defeq to `φ _ •`.
theorem orbit_section_exists (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) :
    ∃ (rep : E → E) (wrd : E → FreeGroup (Fin 2)),
      (∀ x, φ (wrd x) • rep x = x) ∧
      (∀ x (w : FreeGroup (Fin 2)), rep (φ w • x) = rep x)  := by
  letI : MulAction (FreeGroup (Fin 2)) E := MulAction.compHom E φ
  obtain ⟨rep, wrd, h1, h2⟩ :=
    orbit_section_general (G := FreeGroup (Fin 2)) (α := E)
  refine ⟨rep, wrd, ?_, ?_⟩
  · intro x; exact h1 x
  · intro x w; exact h2 x w

-- Build the orbit address from a general orbit section + freeness uniqueness.
-- `orbit_section_exists` gives a representative `rep` and word `wrd` with
-- `φ (wrd x) • rep x = x` and `rep` constant on each F₂-orbit (no freeness/M needed —
-- pure Quotient.out on the orbit relation). The cocycle word equation
-- `wrd (φ w • x) = w * wrd x` then follows from freeness uniqueness on M
-- (`free_action_word_unique`): both `φ (wrd (φ w•x)) • rep x` and `φ (w * wrd x) • rep x`
-- equal `φ w • x`, and `rep x ∈ M`, so the stabilizing words coincide. Each sub-goal is
-- strictly simpler: the section drops the cocycle equation and all M-hypotheses; the
-- uniqueness lemma is a single hfree application with no Equidecomp/orbit structure.
theorem orbit_address_of_free_action
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x) :
    ∃ (rep : E → E) (wrd : E → FreeGroup (Fin 2)),
      (∀ x ∈ M, x = φ (wrd x) • rep x) ∧
      (∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x)  := by
  obtain ⟨rep, wrd, haddr, hrep⟩ := orbit_section_exists φ
  have word_unique := free_action_word_unique φ M hfree
  refine ⟨rep, wrd, fun x _ => (haddr x).symm, fun x hx w => ⟨hrep x w, ?_⟩⟩
  have hr : (φ (wrd x))⁻¹ • x = rep x := by
    rw [inv_smul_eq_iff]; exact (haddr x).symm
  have hrepM : rep x ∈ M := by
    rw [← hr, ← map_inv]
    exact hinv _ _ hx
  have e1 : φ (wrd (φ w • x)) • rep x = φ w • x := by
    rw [← hrep x w]; exact haddr (φ w • x)
  have e2 : φ (w * wrd x) • rep x = φ w • x := by
    rw [map_mul, mul_smul, haddr x]
  exact word_unique (rep x) hrepM _ _ (e1.trans e2.symm)

-- φ w preserves sphere\D: on-sphere via the isometry φ w fixing 0; off-D via conjugation.
-- If φ v fixed φ w • x for some v ≠ 1, then w⁻¹vw (≠ 1) fixes x, so x ∈ D — contradiction.
-- Direct sorry-free proof (no sub-goals): `map_mul`/`map_inv`/`symm_apply_apply` + `group`.
theorem sphere_fixed_action_invariant
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0) :
    ∀ (w : FreeGroup (Fin 2)) (x : E),
        x ∈ Metric.sphere (0 : E) 1 \
            (⋃ (v : FreeGroup (Fin 2)) (_ : v ≠ 1),
                {y ∈ Metric.sphere (0 : E) 1 | φ v y = y}) →
        φ w • x ∈ Metric.sphere (0 : E) 1 \
            (⋃ (v : FreeGroup (Fin 2)) (_ : v ≠ 1),
                {y ∈ Metric.sphere (0 : E) 1 | φ v y = y})  := by
  intro w x hx
  obtain ⟨hx_sph, hx_notD⟩ := hx
  refine ⟨?_, ?_⟩
  · -- φ w • x stays on the sphere: φ w is an isometry fixing 0
    simp only [Metric.mem_sphere] at hx_sph ⊢
    change dist (φ w x) 0 = 1
    rw [← hfix0 w, (φ w).dist_eq]
    exact hx_sph
  · -- φ w • x stays out of D, by the conjugation argument
    intro hmem
    apply hx_notD
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at hmem ⊢
    obtain ⟨v, hv, _, hv_fix⟩ := hmem
    change (φ v) ((φ w) x) = (φ w) x at hv_fix
    refine ⟨w⁻¹ * v * w, ?_, hx_sph, ?_⟩
    · intro hone
      apply hv
      have hvc : v = w * (w⁻¹ * v * w) * w⁻¹ := by group
      rw [hvc, hone]; group
    · show φ (w⁻¹ * v * w) x = x
      rw [map_mul, map_mul]
      change (φ w⁻¹) ((φ v) ((φ w) x)) = x
      rw [hv_fix, map_inv]
      change (φ w).symm ((φ w) x) = x
      exact (φ w).symm_apply_apply x

-- sphere_fixed_union_countable: countable union of finite fixed-point fibers
-- FreeGroup (Fin 2) is countable; each fiber {x | φ w x = x} is finite by hfin.
theorem sphere_fixed_union_countable
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfin : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite) :
    (⋃ (w : FreeGroup (Fin 2)) (_ : w ≠ 1),
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}).Countable := by
  apply Set.countable_iUnion
  intro w
  by_cases hw : w = 1
  · simp [hw]
  · exact (hfin w hw).countable.mono (Set.iUnion_subset fun _ => subset_refl _)

-- Take D := the union, over nontrivial words w, of the fixed points of φ w on the unit sphere:
--   D = ⋃ (w ≠ 1) {x ∈ sphere 0 1 | φ w x = x}. Combinator: `refine ⟨D, …⟩` with five branches.
-- Sub-goal `sphere_fixed_union_countable` (Builder) — D is countable: the index FreeGroup (Fin 2)
--   is countable and each fiber is finite (hfin), so the union is countable; this drops all
--   action/geometry reasoning, hence strictly simpler.
-- Sub-goal `sphere_fixed_action_invariant` (Backward) — φ w • x ∈ sphere \ D for x ∈ sphere \ D:
--   φ w fixes 0 ⇒ it preserves the sphere, and the conjugation argument (w⁻¹vw fixes x whenever
--   v fixes φ w x) keeps φ w • x out of D; isolates a single conjunct of the parent.
-- The remaining three branches are immediate from the definition and closed inline:
--   D ⊆ sphere (each member set is a sphere subset); 0 ∉ D (0 ∉ sphere 0 1); freeness off D
--   (a fixed point on the sphere would itself lie in D, contradicting x ∉ D).
theorem fixed_free_action_off_countable
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (hfin : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite) :
    ∃ D : Set E, D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      (∀ (w : FreeGroup (Fin 2)) (x : E),
          x ∈ Metric.sphere (0 : E) 1 \ D → φ w • x ∈ Metric.sphere (0 : E) 1 \ D) ∧
      (∀ (w : FreeGroup (Fin 2)), w ≠ 1 →
          ∀ x ∈ Metric.sphere (0 : E) 1 \ D, φ w • x ≠ x)  := by
  classical
  refine ⟨⋃ (w : FreeGroup (Fin 2)) (_ : w ≠ 1),
      {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}, ?_, ?_, ?_, ?_, ?_⟩

  · -- countable
    exact sphere_fixed_union_countable φ hfin
  · -- D ⊆ sphere
    intro x hx
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at hx
    obtain ⟨w, _, hx, _⟩ := hx
    exact hx
  · -- 0 ∉ D
    intro h0
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at h0
    obtain ⟨w, _, h0, _⟩ := h0
    rw [Metric.mem_sphere, dist_self] at h0
    exact zero_ne_one h0
  · -- invariance
    exact sphere_fixed_action_invariant φ hfix0
  · -- free off D
    intro w hw x hx hfx
    apply hx.2
    simp only [Set.mem_iUnion, Set.mem_setOf_eq]
    exact ⟨w, hw, hx.1, hfx⟩

-- Direct set-extensionality leaf: the cone over the unit sphere with radii in (0,1]
-- is exactly the punctured closed unit ball. (⊆) `‖r•x‖ = r·1 = r ≤ 1` and `r•x ≠ 0`
-- since `r > 0`, `‖x‖ = 1`; (⊇) for `y ≠ 0`, take `r = ‖y‖ ∈ (0,1]`, `x = ‖y‖⁻¹•y`
-- (`‖x‖ = 1`), then `‖y‖ • ‖y‖⁻¹ • y = y`. Pure normed-space algebra — no sub-goals.
theorem cone_over_sphere_eq_punctured_ball :
    { y : E | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ Metric.sphere (0 : E) 1, y = r • x }
      = Metric.closedBall (0 : E) 1 \ {0}  := by
  ext y
  simp only [Set.mem_setOf_eq, Set.mem_diff, Metric.mem_closedBall, dist_zero_right,
    Metric.mem_sphere, Set.mem_singleton_iff]
  constructor
  · rintro ⟨r, ⟨hr0, hr1⟩, x, hx, rfl⟩
    refine ⟨?_, ?_⟩
    · rw [norm_smul, Real.norm_eq_abs, abs_of_pos hr0, hx, mul_one]; exact hr1
    · exact smul_ne_zero (ne_of_gt hr0) (by rw [← norm_pos_iff, hx]; norm_num)
  · rintro ⟨hy1, hy0⟩
    have hyn : 0 < ‖y‖ := norm_pos_iff.mpr hy0
    refine ⟨‖y‖, ⟨hyn, hy1⟩, ‖y‖⁻¹ • y, ?_, ?_⟩
    · rw [norm_smul, norm_inv, Real.norm_eq_abs, abs_norm,
        inv_mul_cancel₀ (ne_of_gt hyn)]
    · rw [smul_smul, mul_inv_cancel₀ (ne_of_gt hyn), one_smul]

-- entry_kind: Builder
-- cone_distrib_union: the radial cone distributes over set unions (pure set algebra)
theorem cone_distrib_union (A B : Set E) :
    {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A ∪ B, y = r • x}
      = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A, y = r • x}
        ∪ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ B, y = r • x} := by
  ext y
  simp only [Set.mem_setOf_eq, Set.mem_union]
  constructor
  · rintro ⟨r, hr, x, hx | hx, hy⟩
    · left; exact ⟨r, hr, x, hx, hy⟩
    · right; exact ⟨r, hr, x, hx, hy⟩
  · rintro (⟨r, hr, x, hx, hy⟩ | ⟨r, hr, x, hx, hy⟩)
    · exact ⟨r, hr, x, Or.inl hx, hy⟩
    · exact ⟨r, hr, x, Or.inr hx, hy⟩

-- entry_kind: Builder
-- cone_preserves_disjoint: disjoint cone lifts when sphere base sets are disjoint,
-- by recovering the unique unit direction via r = ‖y‖ (since ‖x‖=1, r>0)
theorem cone_preserves_disjoint (A B : Set E)
    (hA : A ⊆ Metric.sphere (0 : E) 1) (hB : B ⊆ Metric.sphere (0 : E) 1)
    (hdisj : Disjoint A B) :
    Disjoint {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A, y = r • x}
             {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ B, y = r • x} := by
  rw [Set.disjoint_left]
  intro y ⟨r₁, hr₁, x₁, hx₁A, hy₁⟩ ⟨r₂, hr₂, x₂, hx₂B, hy₂⟩
  have hx₁n : ‖x₁‖ = 1 := by
    have := hA hx₁A; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hx₂n : ‖x₂‖ = 1 := by
    have := hB hx₂B; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hr₁pos : (0 : ℝ) < r₁ := hr₁.1
  have hr₂pos : (0 : ℝ) < r₂ := hr₂.1
  have hr₁eq : ‖y‖ = r₁ := by
    rw [hy₁, norm_smul, Real.norm_of_nonneg hr₁pos.le, hx₁n, mul_one]
  have hr₂eq : ‖y‖ = r₂ := by
    rw [hy₂, norm_smul, Real.norm_of_nonneg hr₂pos.le, hx₂n, mul_one]
  have hrr : r₁ = r₂ := hr₁eq.symm.trans hr₂eq
  have hx_eq : x₁ = x₂ := by
    have h : r₁ • x₁ = r₁ • x₂ := hy₁.symm.trans (hrr ▸ hy₂)
    have := congr_arg (r₁⁻¹ • ·) h
    simp only [smul_smul, inv_mul_cancel₀ hr₁pos.ne', one_smul] at this
    exact this
  exact Set.disjoint_left.mp hdisj hx₁A (hx_eq ▸ hx₂B)

-- S realizes the cone map: each cone point y = r•x (r∈(0,1], x∈e.source⊆sphere) has ‖y‖=r,
-- ‖y‖⁻¹•y = x, so f y = r • e x = r • (g•x) for the g∈S realizing e at x; since g fixes 0 it is
-- ℝ-linear (isometry_fixing_origin_smul_comm), so g•(r•x) = r•(g•x), matching. Leaf: cite isometry_fixing_origin_smul_comm + norm algebra inline.
theorem cone_is_decomp (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    Equidecomp.IsDecompOn (fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z))
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} S  := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  obtain ⟨g, hgS, hgx⟩ := hdec x hx
  refine ⟨g, hgS, ?_⟩
  have hx1 : ‖x‖ = 1 := by
    have h := hsrc hx
    rwa [mem_sphere_zero_iff_norm] at h
  have hrpos : 0 < r := hr.1
  have hnr : ‖r • x‖ = r := by
    rw [norm_smul, hx1, mul_one, Real.norm_eq_abs, abs_of_pos hrpos]
  have hxback : (‖r • x‖)⁻¹ • (r • x) = x := by
    rw [hnr, smul_smul, inv_mul_cancel₀ (ne_of_gt hrpos), one_smul]
  change ‖r • x‖ • e.toFun (‖r • x‖⁻¹ • (r • x)) = g • (r • x)
  rw [hxback, hnr, hgx]
  change r • (g x) = g (r • x)
  rw [isometry_fixing_origin_smul_comm g (h0 g hgS) r x]

-- entry_kind: Builder
-- cone_left_inv: radial-lift left-inverse via sphere norm = 1 and PartialEquiv.left_inv'
-- For y = r•x with x on the unit sphere (e.source), normalize by ‖y‖=r, apply e then e.invFun.
theorem cone_left_inv (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} →
      (fun z => ‖z‖ • e.invFun (‖z‖⁻¹ • z))
        ((fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z)) y) = y := by
    intro y hy
    obtain ⟨r, hr, x, hx, rfl⟩ := hy
    simp only []
    have hxnorm : ‖x‖ = 1 := by
      have := hsrc hx; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hr_pos : 0 < r := hr.1
    have hr_ne : r ≠ 0 := hr_pos.ne'
    have hrnorm : ‖r • x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hxnorm, mul_one]
    rw [hrnorm]
    have hinvx : r⁻¹ • (r • x) = x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvx]
    have htgt_mem : e.toFun x ∈ e.target := e.map_source' hx
    have hetgnorm : ‖e.toFun x‖ = 1 := by
      have := htgt htgt_mem; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hretnorm : ‖r • e.toFun x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hetgnorm, mul_one]
    rw [hretnorm]
    have hinvet : r⁻¹ • (r • e.toFun x) = e.toFun x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvet]
    have hleft : e.invFun (e.toFun x) = x := e.left_inv' hx
    rw [hleft]

-- cone_map_source: radial cone image lands in cone of target (uses map_source + ‖x‖=1 on sphere)
-- If y = r•x with x ∈ e.source ⊆ sphere and r ∈ (0,1], then ‖y‖=r, ‖y‖⁻¹•y = x, so
-- ‖y‖•e(‖y‖⁻¹•y) = r•e(x) ∈ cone of e.target by e.map_source.
theorem cone_map_source (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} →
      ‖y‖ • e.toFun (‖y‖⁻¹ • y) ∈
        {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  have hxnorm : ‖x‖ = 1 := by
    have h := hsrc hx
    simp only [Metric.mem_sphere, dist_zero_right] at h
    exact h
  have hrnorm : ‖r • x‖ = r := by
    rw [norm_smul, Real.norm_of_nonneg (le_of_lt hr.1), hxnorm, mul_one]
  have hinv : r⁻¹ • r • x = x := inv_smul_smul₀ (ne_of_gt hr.1) x
  rw [hrnorm, hinv]
  exact ⟨r, hr, e.toFun x, e.map_source hx, rfl⟩

-- cone_map_target: radial cone image lands in the cone of e.source via e.invFun + norm algebra
-- y = r•x (x ∈ e.target, r ∈ (0,1]); ‖y‖ = r (since x on unit sphere); ‖y‖⁻¹•y = x;
-- e.invFun x ∈ e.source; conclusion r • e.invFun x in cone of e.source.
-- entry_kind: Builder
theorem cone_map_target (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} →
      ‖y‖ • e.invFun (‖y‖⁻¹ • y) ∈
        {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} := by
    intro y hy
    simp only [Set.mem_setOf_eq] at hy ⊢
    obtain ⟨r, hr, x, hx, rfl⟩ := hy
    have hxs : x ∈ Metric.sphere (0 : E) 1 := htgt hx
    have hxnorm : ‖x‖ = 1 := by rwa [Metric.mem_sphere, dist_zero_right] at hxs
    have hrpos : (0 : ℝ) < r := hr.1
    have hnorm : ‖r • x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hrpos.le, hxnorm, mul_one]
    have hef : e.invFun x ∈ e.source := e.map_target' hx
    exact ⟨r, hr, e.invFun x, hef, by rw [hnorm]; congr 1; rw [inv_smul_smul₀ hrpos.ne']⟩

-- cone_right_inv: radial-lift right-inverse via sphere norm = 1 and PartialEquiv.right_inv'
-- cone_right_inv: radial-lift right-inverse via sphere norm = 1 and PartialEquiv.right_inv'
-- For y = r•x with x ∈ e.target (unit sphere), normalize by ‖y‖=r, apply invFun then toFun.

theorem cone_right_inv (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} →
      (fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z))
        ((fun z => ‖z‖ • e.invFun (‖z‖⁻¹ • z)) y) = y := by
    intro y hy
    obtain ⟨r, hr, x, hx, rfl⟩ := hy
    simp only []
    have hxnorm : ‖x‖ = 1 := by
      have := htgt hx; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hr_pos : 0 < r := hr.1
    have hr_ne : r ≠ 0 := hr_pos.ne'
    have hrnorm : ‖r • x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hxnorm, mul_one]
    rw [hrnorm]
    have hinvx : r⁻¹ • (r • x) = x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvx]
    have hsrc_mem : e.invFun x ∈ e.source := e.map_target' hx
    have hinvnorm : ‖e.invFun x‖ = 1 := by
      have := hsrc hsrc_mem; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hreinvnorm : ‖r • e.invFun x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hinvnorm, mul_one]
    rw [hreinvnorm]
    have hinvinv : r⁻¹ • (r • e.invFun x) = e.invFun x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvinv]
    have hright : e.toFun (e.invFun x) = x := e.right_inv' hx
    rw [hright]

-- Cone-lift functor: radially extend the sphere Equidecomp `e` to its cone (0,1]·e.
-- Realizing map  y ↦ ‖y‖ • e (‖y‖⁻¹ • y)  (and its inverse via e.invFun); since e's
-- decomposition isometries fix 0 they commute with radial scaling, so the SAME finite
-- witness set S realizes the cone map. Assemble via Equidecomp.mk ∘ PartialEquiv.mk;
-- source/target are the cone sets definitionally (rfl). The five structure obligations
-- are farmed as standalone sub-goals, each strictly simpler than the existential assembly:
--  • cone_map_source / cone_map_target — radial image lands in the cone of e.target/e.source
--  • cone_left_inv / cone_right_inv     — the radial map and its radial inverse cancel
--  • cone_is_decomp                     — S realizes the cone map (origin-fixing ⇒ equivariant)

theorem cone_lift_equidecomp (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S)
    (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∃ e' : Equidecomp E (E ≃ᵢ E),
      e'.source = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} ∧
      e'.target = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x}  := by
  refine ⟨Equidecomp.mk (PartialEquiv.mk
      (fun y => ‖y‖ • e.toFun (‖y‖⁻¹ • y))
      (fun y => ‖y‖ • e.invFun (‖y‖⁻¹ • y))
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x}
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x}
      ?hms ?hmt ?hli ?hri) ⟨S, ?hdec⟩, rfl, rfl⟩
  case hms => exact cone_map_source e S hdec h0 hsrc htgt
  case hmt => exact cone_map_target e S hdec h0 hsrc htgt
  case hli => exact cone_left_inv e S hdec h0 hsrc htgt
  case hri => exact cone_right_inv e S hdec h0 hsrc htgt
  case hdec => exact cone_is_decomp e S hdec h0 hsrc htgt

-- entry_kind: Backward
-- wrd_of_tower_image: FreeGroup cohomology — word address of tower image equals group power
-- For z = (φ(of 1)⁻¹)^k • x with wrd x = 1 (head? = none), hcoh gives wrd z = (of 1)⁻¹^k * 1.
theorem wrd_of_tower_image
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x)
    (k : ℕ) (z : E)
    (hz : z ∈ ((φ (FreeGroup.of 1))⁻¹ ^ k) ''
        {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}) :
    wrd z = ((FreeGroup.of (1:Fin 2))⁻¹) ^ k := by
  obtain ⟨x, ⟨hxM, hhead⟩, rfl⟩ := hz
  have hnil : FreeGroup.toWord (wrd x) = [] := by
    cases h : FreeGroup.toWord (wrd x) with
    | nil => rfl
    | cons a t => simp [h] at hhead
  have hwrd_x : wrd x = 1 := by
    apply FreeGroup.toWord_injective
    rw [hnil, FreeGroup.toWord_one]
  have hkey : ((φ (FreeGroup.of 1))⁻¹ ^ k) x =
      φ ((FreeGroup.of (1:Fin 2))⁻¹ ^ k) • x := by
    simp only [map_pow, map_inv]; rfl
  rw [hkey]
  have hcoh2 := (hcoh x hxM ((FreeGroup.of (1:Fin 2))⁻¹ ^ k)).2
  rw [hwrd_x, mul_one] at hcoh2
  exact hcoh2

-- Orbit tower D, ρ^i''D (ρ = φ(of 1)⁻¹), is pairwise disjoint because the
-- address `wrd` of any element of ρ^i''D equals (of 1)⁻¹^i (hcoh: wrd(φ w•x)=w*wrd x,
-- with wrd x=1 on D since head?=none), and the reduced word (of 1)⁻¹^i has length i —
-- a strictly-increasing invariant, so i≠j ⇒ disjoint.
-- Sub-goals: `wrd_of_tower_image` (address of a tower element) and
-- `length_pow_inv_of` (length of the pure FreeGroup power). Combiner: a shared y
-- forces (of 1)⁻¹^i = (of 1)⁻¹^j, take toWord-length to get i = j ⊥ hij.
theorem orbit_tower_disjoint
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    Pairwise (fun i j : ℕ => Disjoint
        (((φ (FreeGroup.of 1))⁻¹ ^ i) ''
          {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none})
        (((φ (FreeGroup.of 1))⁻¹ ^ j) ''
          {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}))  := by
  intro i j hij
  rw [Set.disjoint_left]
  rintro y hyi hyj
  apply hij
  have key : ((FreeGroup.of (1:Fin 2))⁻¹) ^ i = ((FreeGroup.of (1:Fin 2))⁻¹) ^ j :=
    (wrd_of_tower_image φ M rep wrd hcoh i y hyi).symm.trans
      (wrd_of_tower_image φ M rep wrd hcoh j y hyj)
  have hcong := congrArg (fun w => (FreeGroup.toWord w).length) key
  simpa [length_pow_inv_of] using hcong

-- entry_kind: Builder
-- source_diff_eq_target: set difference eliminates head?=none, leaving exactly head?=some(1,_)
-- Fin 2 has values 0,1; excluding none and some(0,_) leaves some(1,true/false).
theorem source_diff_eq_target (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} \
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}
    = {x | x ∈ M ∧
        ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
         (FreeGroup.toWord (wrd x)).head? = some (1, false))} := by
  ext x

  simp only [Set.mem_diff, Set.mem_setOf_eq]
  constructor
  · rintro ⟨⟨hm, hneq0⟩, hnone⟩
    refine ⟨hm, ?_⟩
    rcases h : (FreeGroup.toWord (wrd x)).head? with _ | ⟨⟨i, b⟩⟩
    · exact absurd ⟨hm, h⟩ hnone
    · have hine : i ≠ 0 := by
        intro hi
        apply hneq0
        simp [h, hi]
      have hi1 : i = 1 := by fin_cases i <;> simp_all
      subst hi1
      cases b
      · right; rfl
      · left; rfl
  · rintro ⟨hm, h | h⟩
    · constructor
      · exact ⟨hm, by simp [h]⟩
      · rintro ⟨-, hn⟩; simp [h] at hn
    · constructor
      · exact ⟨hm, by simp [h]⟩
      · rintro ⟨-, hn⟩; simp [h] at hn

-- Tower ⊆ source: each tower element ((φ(of 1))⁻¹^n) y with y an empty-word rep
-- equals φ((of 1)⁻¹^n) • y, so it lands in M (hinv) and its representative word is
-- (of 1)⁻¹^n (hcoh + wrd y = 1 from h_empty), whose first letter is never (0,_).
-- Sub-goals: tower_first_letter_ne_zero (free-group combinatorics, head of (of 1)⁻¹^n)
-- and empty_word_head_eq_one (head?=none ⇒ word is 1). Both are parameter-free and
-- strictly simpler than the set-inclusion parent.
theorem tower_subset_source
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    (⋃ n : ℕ, ((φ (FreeGroup.of 1))⁻¹ ^ n) ''
        {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none})
      ⊆ {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}  := by
  intro x hx
  simp only [Set.mem_iUnion, Set.mem_image] at hx
  obtain ⟨n, y, ⟨hyM, hyhead⟩, rfl⟩ := hx
  have h_tower := tower_first_letter_ne_zero
  have h_empty := empty_word_head_eq_one

  have hbridge : ((φ (FreeGroup.of 1))⁻¹ ^ n) y = φ ((FreeGroup.of 1)⁻¹ ^ n) • y := by
    rw [map_pow, map_inv]; rfl
  rw [Set.mem_setOf_eq, hbridge]
  refine ⟨hinv _ _ hyM, ?_⟩
  have hwrd : wrd (φ ((FreeGroup.of 1)⁻¹ ^ n) • y) = (FreeGroup.of 1)⁻¹ ^ n := by
    rw [(hcoh y hyM ((FreeGroup.of 1)⁻¹ ^ n)).2, h_empty (wrd y) hyhead, mul_one]
  rw [hwrd]
  exact h_tower n

-- The four PartialEquiv laws for the letter-0 piece: f = id on A / g0•· off A,
-- g = id on A / g0⁻¹•· off A.
-- Direct case split on A vs B using only: hsplit (g0•B = M\A), Disjoint A B, A ⊆ M, and the
-- group-action laws inv_smul_smul / smul_inv_smul. No nontrivial sub-claim — ships as a leaf.
theorem letter0_partial_equiv_laws
    (A B M : Set E) (g0 : E ≃ᵢ E) (f g : E → E)
    (hAM : A ⊆ M)
    (hAB : Disjoint A B)
    (hsplit : (fun x => g0 • x) '' B = M \ A)
    (hfA : ∀ x ∈ A, f x = x)
    (hfnA : ∀ x, x ∉ A → f x = g0 • x)
    (hgA : ∀ y ∈ A, g y = y)
    (hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y) :
    (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y)  := by
  have hBnA : ∀ x ∈ B, x ∉ A := fun x hx => (Set.disjoint_right.mp hAB) hx
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro x hx
    rcases hx with hx | hx
    · rw [hfA x hx]; exact hAM hx
    · rw [hfnA x (hBnA x hx)]
      have h : g0 • x ∈ M \ A := by rw [← hsplit]; exact ⟨x, hx, rfl⟩
      exact h.1
  · intro y hy
    by_cases hyA : y ∈ A
    · rw [hgA y hyA]; exact Or.inl hyA
    · rw [hgnA y hyA]
      have hyMA : y ∈ M \ A := ⟨hy, hyA⟩
      rw [← hsplit] at hyMA
      obtain ⟨b, hb, hbeq⟩ := hyMA
      refine Or.inr ?_
      have : g0⁻¹ • y = b := by rw [← hbeq]; simp
      rw [this]; exact hb
  · intro x hx
    rcases hx with hx | hx
    · rw [hfA x hx, hgA x hx]
    · rw [hfnA x (hBnA x hx)]
      have h : g0 • x ∈ M \ A := by rw [← hsplit]; exact ⟨x, hx, rfl⟩
      rw [hgnA (g0 • x) h.2]; simp
  · intro y hy
    by_cases hyA : y ∈ A
    · rw [hgA y hyA, hfA y hyA]
    · rw [hgnA y hyA]
      have hyMA : y ∈ M \ A := ⟨hy, hyA⟩
      rw [← hsplit] at hyMA
      obtain ⟨b, hb, hbeq⟩ := hyMA
      have hinv : g0⁻¹ • y = b := by rw [← hbeq]; simp
      rw [hinv, hfnA b (hBnA b hb)]
      exact hbeq

-- entry_kind: Builder
theorem letter0_pieces_disjoint (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    Disjoint {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} := by grind

-- entry_kind: Builder
theorem letter0_source_eq_union (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}
      = {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}
        ∪ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} := by aesop

-- Transport the F₂ identity `a·Wₐ⁻¹ = F₂\Wₐ` to point sets via the equivariant `wrd`.
-- The bijection `x ↦ φ(of 0)•x` on M has inverse `y ↦ φ((of 0)⁻¹)•y` (group/action algebra,
-- inline). Its only genuine-math content is the head-flip `letter0_head_flip`: for z∈M, the
-- word of `φ((of 0)⁻¹)•z` starts with `(0,false)` iff that of `z` does not start with `(0,true)`
-- (just `hwrd` + the proved sibling `head_inv_mul_iff`). Set.ext + this iff close both inclusions.
theorem letter0_split
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x) :
    (fun x => φ (FreeGroup.of 0) • x) ''
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)}
      = M \ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}  := by
  have key : ∀ z ∈ M,
      (FreeGroup.toWord (wrd (φ ((FreeGroup.of 0)⁻¹) • z))).head? = some (0, false)
        ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (0, true) :=
    fun z hz => letter0_head_flip φ M wrd hwrd z hz

  ext y
  simp only [Set.mem_image, Set.mem_setOf_eq, Set.mem_diff]
  constructor
  · rintro ⟨x, ⟨hxM, hxhead⟩, rfl⟩
    refine ⟨hinv _ _ hxM, ?_⟩
    rintro ⟨_, hhead⟩
    have hyM : φ (FreeGroup.of 0) • x ∈ M := hinv _ _ hxM
    have hxy : φ ((FreeGroup.of 0)⁻¹) • (φ (FreeGroup.of 0) • x) = x := by
      rw [smul_smul, ← map_mul, inv_mul_cancel, map_one, one_smul]
    have hk := key _ hyM
    rw [hxy] at hk
    exact (hk.mp hxhead) hhead
  · rintro ⟨hyM, hyhead⟩
    refine ⟨φ ((FreeGroup.of 0)⁻¹) • y, ⟨hinv _ _ hyM, ?_⟩, ?_⟩
    · rw [key y hyM]
      intro hc
      exact hyhead ⟨hyM, hc⟩
    · rw [smul_smul, ← map_mul, mul_inv_cancel, map_one, one_smul]

-- entry_kind: Builder
theorem b_letter_pieces_disjoint (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    Disjoint {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)}
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)} := by grind

-- Generator-1 analogue of `letter0_split`/s11482: transport the F₂ identity
-- `b·Wᵦ⁻¹ = M\Wᵦ` to point sets via the equivariant `wrd`. The bijection
-- `x ↦ φ(of 1)•x` on M has inverse `y ↦ φ((of 1)⁻¹)•y` (group/action algebra,
-- inline). Genuine content is the head-flip `key`: `hwrd` + proved sibling
-- `head_inv_mul_iff 1`. `Set.ext` + this iff close both inclusions. No sub-goals.
theorem b_letter_split
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x) :
    (fun x => φ (FreeGroup.of 1) • x) ''
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)}
      = M \ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)}  := by
  have key : ∀ z ∈ M,
      (FreeGroup.toWord (wrd (φ ((FreeGroup.of 1)⁻¹) • z))).head? = some (1, false)
        ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (1, true) := by
    intro z hz
    rw [hwrd z hz]
    exact head_inv_mul_iff 1 (wrd z)
  ext y
  simp only [Set.mem_image, Set.mem_setOf_eq, Set.mem_diff]
  constructor
  · rintro ⟨x, ⟨hxM, hxhead⟩, rfl⟩
    refine ⟨hinv _ _ hxM, ?_⟩
    rintro ⟨_, hhead⟩
    have hyM : φ (FreeGroup.of 1) • x ∈ M := hinv _ _ hxM
    have hxy : φ ((FreeGroup.of 1)⁻¹) • (φ (FreeGroup.of 1) • x) = x := by
      rw [smul_smul, ← map_mul, inv_mul_cancel, map_one, one_smul]
    have hk := key _ hyM
    rw [hxy] at hk
    exact (hk.mp hxhead) hhead
  · rintro ⟨hyM, hyhead⟩
    refine ⟨φ ((FreeGroup.of 1)⁻¹) • y, ⟨hinv _ _ hyM, ?_⟩, ?_⟩
    · rw [key y hyM]
      intro hc
      exact hyhead ⟨hyM, hc⟩
    · rw [smul_smul, ← map_mul, mul_inv_cancel, map_one, one_smul]

-- Origin-fixing refinement of build_letter0_equidecomp (s11472): same piecewise map
-- (f = id on A, g0•· on B, g0 = φ(of 0)) reconstructed inline from the proved bricks,
-- now ALSO exposing the realizing Finset Sf = {1, g0} and proving every element fixes 0.
-- The IsDecompOn witness is the explicit {1, g0} (id-or-shift case split); origin-fixing
-- is (1) 0 = 0 and g0 0 = φ(of 0) 0 = 0 via hfix0. No new sub-goals — leaf reconstruction.
theorem build_letter0_equidecomp_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (f : Equidecomp E (E ≃ᵢ E)) (Sf : Finset (E ≃ᵢ E)),
      f.source = {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      f.target = M ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      (∀ s ∈ Sf, s 0 = 0)  := by
  classical
  set g0 : E ≃ᵢ E := φ (FreeGroup.of 0) with hg0
  set A : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)} with hA
  set B : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} with hB
  set S₀ : Set E :=
    {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} with hS₀def
  set f : E → E := fun x => if x ∈ A then x else g0 • x with hfdef
  set g : E → E := fun y => if y ∈ A then y else g0⁻¹ • y with hgdef
  have hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x :=
    fun x hx w => (hcoh x hx w).2
  have hsplit : (fun x => g0 • x) '' B = M \ A := letter0_split φ M hinv wrd hwrd
  have hS₀ : S₀ = A ∪ B := letter0_source_eq_union M wrd
  have hAB : Disjoint A B := letter0_pieces_disjoint M wrd
  have hAM : A ⊆ M := fun x hx => hx.1
  have hfA : ∀ x ∈ A, f x = x := by intro x hx; simp only [hfdef]; rw [if_pos hx]
  have hfnA : ∀ x, x ∉ A → f x = g0 • x := by intro x hx; simp only [hfdef]; rw [if_neg hx]
  have hgA : ∀ y ∈ A, g y = y := by intro y hy; simp only [hgdef]; rw [if_pos hy]
  have hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y := by intro y hy; simp only [hgdef]; rw [if_neg hy]
  have hlaws : (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) :=
    letter0_partial_equiv_laws A B M g0 f g hAM hAB hsplit hfA hfnA hgA hgnA
  obtain ⟨hms0, hmt0, hli0, hri0⟩ := hlaws
  have hms : ∀ x ∈ S₀, f x ∈ M := by intro x hx; rw [hS₀] at hx; exact hms0 x hx
  have hmt : ∀ y ∈ M, g y ∈ S₀ := by intro y hy; rw [hS₀]; exact hmt0 y hy
  have hli : ∀ x ∈ S₀, g (f x) = x := by intro x hx; rw [hS₀] at hx; exact hli0 x hx
  have hri : ∀ y ∈ M, f (g y) = y := hri0
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  have hdecS : Equidecomp.IsDecompOn f S₀ {1, g0} := by
    rw [hS₀]
    intro a _
    by_cases hA' : a ∈ A
    · exact ⟨1, Finset.mem_insert_self 1 {g0}, by rw [hfA a hA']; simp⟩
    · exact ⟨g0, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)), hfnA a hA'⟩
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f S₀ S := ⟨{1, g0}, hdecS⟩
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g S₀ M hms hmt hli hri) hdec,
    {1, g0}, rfl, rfl, hdecS, ?_⟩
  intro s hs
  rw [Finset.mem_insert, Finset.mem_singleton] at hs
  rcases hs with rfl | rfl
  · rfl
  · exact hfix0 (FreeGroup.of 0)

-- Origin-fixing mirror of absorb_empty_word (s11479): same Hilbert-hotel piecewise
-- map f (ρ := φ(of 1)⁻¹ on the orbit tower T, id off T) realizing source ≃ source\D,
-- but now ALSO expose the realizing Finset {ρ,1} and prove every member fixes 0.
-- The four PartialEquiv laws + the tower/disjoint/shift facts are the proved Hilbert
-- bricks (cited inline); the ONLY new sub-goal is is_decomp_hilbert_origin_fixing_2, which
-- packages the {ρ,1} witness together with ρ 0 = 0 (and 1 0 = 0).  ρ 0 = 0 holds
-- because ρ = φ((of 1)⁻¹) and hfix0 fixes the origin for every φ-image.
theorem absorb_empty_word_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (Sa : Finset (E ≃ᵢ E)),
      e.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      e.target = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))} ∧
      Equidecomp.IsDecompOn e.toFun e.source Sa ∧
      (∀ s ∈ Sa, s 0 = 0)  := by
  classical
  set ρ : E ≃ᵢ E := (φ (FreeGroup.of 1))⁻¹ with hρ_def
  set D : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none} with hD_def
  set A : Set E := {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}
    with hA_def
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hT_def
  set f : E → E := fun x => if x ∈ T then ρ x else x with hf_def
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hg_def
  have hf : ∀ x, x ∈ T → f x = ρ x := by intro x hx; rw [hf_def]; exact if_pos hx
  have hf' : ∀ x, x ∉ T → f x = x := by intro x hx; rw [hf_def]; exact if_neg hx
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := by intro y hy; rw [hg_def]; exact if_pos hy
  have hg' : ∀ y, y ∉ T → g y = y := by intro y hy; rw [hg_def]; exact if_neg hy
  have hDT : D ⊆ T := by
    intro x hx; rw [hT_def]; exact Set.mem_iUnion.mpr ⟨0, x, hx, by simp⟩
  have hTA : T ⊆ A := tower_subset_source φ M hinv rep wrd hcoh
  have hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D)) :=
    orbit_tower_disjoint φ M hinv rep wrd hcoh
  have hshift : ρ '' T = T \ D := hotel_shift D ρ hdisj
  have hAD : A \ D = {x | x ∈ M ∧
      ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
       (FreeGroup.toWord (wrd x)).head? = some (1, false))} := source_diff_eq_target M wrd
  have hms : ∀ x ∈ A, f x ∈ A \ D := map_source_hilbert A D T ρ f hf hf' hDT hTA hshift
  have hmt : ∀ y ∈ A \ D, g y ∈ A := map_target_hilbert A D T ρ g hg hg' hDT hTA hshift
  have hli : ∀ x ∈ A, g (f x) = x := left_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hri : ∀ y ∈ A \ D, f (g y) = y := right_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hρ0 : ρ 0 = 0 := by
    have heq : ρ = φ ((FreeGroup.of 1)⁻¹) := by rw [hρ_def, map_inv]
    rw [heq]; exact hfix0 _
  obtain ⟨S, hSdec, hSfix⟩ := is_decomp_hilbert_origin_fixing_2 A T ρ f hf hf' hρ0
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) ⟨S, hSdec⟩,
    S, rfl, hAD, hSdec, hSfix⟩

-- Origin-fixing refinement of b_letter_equidecomp (s11480): generator-1 piecewise map
-- (f = id on A=Wᵦ, g0•· on B=Wᵦ⁻¹, g0 = φ(of 1)) reconstructed inline from the proved
-- bricks (b_letter_split, b_letter_pieces_disjoint, letter0_partial_equiv_laws), now ALSO
-- exposing the realizing Finset Sb = {1, g0} and proving every element fixes 0 (1 0 = 0;
-- g0 0 = φ(of 1) 0 = 0 via hfix0).  No new sub-goals — leaf reconstruction.
theorem b_letter_equidecomp_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (Sb : Finset (E ≃ᵢ E)),
      e.source = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))} ∧
      e.target = M ∧
      Equidecomp.IsDecompOn e.toFun e.source Sb ∧
      (∀ s ∈ Sb, s 0 = 0)  := by
  classical
  set g0 : E ≃ᵢ E := φ (FreeGroup.of 1) with hg0
  set A : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)} with hA
  set B : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)} with hB
  set Src : Set E :=
    {x | x ∈ M ∧ ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
        (FreeGroup.toWord (wrd x)).head? = some (1, false))} with hSrcdef
  set f : E → E := fun x => if x ∈ A then x else g0 • x with hfdef
  set g : E → E := fun y => if y ∈ A then y else g0⁻¹ • y with hgdef
  have hsplit : (fun x => g0 • x) '' B = M \ A :=
    b_letter_split φ M hinv wrd (fun x hxM w => (hcoh x hxM w).2)
  have hSrc : Src = A ∪ B := by
    ext x
    simp only [hSrcdef, hA, hB, Set.mem_setOf_eq, Set.mem_union]
    tauto
  have hAB : Disjoint A B := b_letter_pieces_disjoint M wrd
  have hAM : A ⊆ M := fun x hx => hx.1
  have hfA : ∀ x ∈ A, f x = x := by intro x hx; simp only [hfdef]; rw [if_pos hx]
  have hfnA : ∀ x, x ∉ A → f x = g0 • x := by intro x hx; simp only [hfdef]; rw [if_neg hx]
  have hgA : ∀ y ∈ A, g y = y := by intro y hy; simp only [hgdef]; rw [if_pos hy]
  have hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y := by intro y hy; simp only [hgdef]; rw [if_neg hy]
  have hlaws : (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) :=
    letter0_partial_equiv_laws A B M g0 f g hAM hAB hsplit hfA hfnA hgA hgnA
  obtain ⟨hms0, hmt0, hli0, hri0⟩ := hlaws
  have hms : ∀ x ∈ Src, f x ∈ M := by intro x hx; rw [hSrc] at hx; exact hms0 x hx
  have hmt : ∀ y ∈ M, g y ∈ Src := by intro y hy; rw [hSrc]; exact hmt0 y hy
  have hli : ∀ x ∈ Src, g (f x) = x := by intro x hx; rw [hSrc] at hx; exact hli0 x hx
  have hri : ∀ y ∈ M, f (g y) = y := hri0
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  have hdecS : Equidecomp.IsDecompOn f Src {1, g0} := by
    rw [hSrc]
    intro a _
    by_cases hA' : a ∈ A
    · exact ⟨1, Finset.mem_insert_self 1 {g0}, by rw [hfA a hA']; simp⟩
    · exact ⟨g0, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)), hfnA a hA'⟩
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f Src S := ⟨{1, g0}, hdecS⟩
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g Src M hms hmt hli hri) hdec,
    {1, g0}, rfl, rfl, hdecS, ?_⟩
  intro s hs
  rw [Finset.mem_insert, Finset.mem_singleton] at hs
  rcases hs with rfl | rfl
  · rfl
  · exact hfix0 (FreeGroup.of 1)

-- Trans-glue of two origin-fixing equidecompositions: witness e := e₁.trans e₂,
-- realizing Finset S := S₂ ⋆ S₁ (Finset.image₂ (·*·)). Source/target come from the
-- PartialEquiv.trans laws; IsDecompOn from per-factor decomp + mul_smul; origin-fixing
-- since (g₂*g₁) 0 = g₂ (g₁ 0) = g₂ 0 = 0. Self-contained leaf.
theorem equidecomp_trans_glue_origin_fixing
    (e₁ e₂ : Equidecomp E (E ≃ᵢ E)) (h : e₁.target = e₂.source)
    (S₁ S₂ : Finset (E ≃ᵢ E))
    (hd₁ : Equidecomp.IsDecompOn e₁.toFun e₁.source S₁)
    (hd₂ : Equidecomp.IsDecompOn e₂.toFun e₂.source S₂)
    (h0₁ : ∀ s ∈ S₁, s 0 = 0) (h0₂ : ∀ s ∈ S₂, s 0 = 0) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E)),
      e.source = e₁.source ∧ e.target = e₂.target ∧
      Equidecomp.IsDecompOn e.toFun e.source S ∧
      (∀ s ∈ S, s 0 = 0)  := by
  classical
  refine ⟨e₁.trans e₂, Finset.image₂ (· * ·) S₂ S₁, ?_, ?_, ?_, ?_⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source]
    rw [← h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx; exact ⟨hx, e₁.map_source' hx⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_target]
    rw [h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx; exact ⟨hx, e₂.map_target' hx⟩
  · intro a ha
    rw [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source] at ha
    obtain ⟨ha1, ha2⟩ := ha
    obtain ⟨g₁, hg₁, hfa⟩ := hd₁ a ha1
    obtain ⟨g₂, hg₂, hfb⟩ := hd₂ (e₁.toFun a) ha2
    refine ⟨g₂ * g₁, Finset.mem_image₂_of_mem hg₂ hg₁, ?_⟩
    change e₂.toFun (e₁.toFun a) = (g₂ * g₁) • a
    rw [hfb, hfa, mul_smul]
  · intro s hs
    obtain ⟨g₂, hg₂, g₁, hg₁, rfl⟩ := Finset.mem_image₂.mp hs
    calc (g₂ * g₁) 0 = g₂ (g₁ 0) := rfl
      _ = g₂ 0 := by rw [h0₁ g₁ hg₁]
      _ = 0 := h0₂ g₂ hg₂

-- Origin-fixing mirror of build_non_letter0_equidecomp (s11473): the non-letter-0 piece is
-- the trans-composition absorb_empty_word ∘ b_letter_equidecomp.  Each factor is refined to
-- ALSO expose its origin-fixing realizing Finset (absorb: {φ(of 1)⁻¹,1}; b-letter: {1,φ(of 1)},
-- all fixing 0 via hfix0), and a generic origin-fixing trans-glue composes them: the composite
-- Finset = S₂ * S₁ (products of the per-step shifts), each a product of origin-fixers ⇒ fixes 0.
-- Sub-goals: (1) absorb_empty_word_origin_fixing, (2) b_letter_equidecomp_origin_fixing,
-- (3) equidecomp_trans_glue_origin_fixing (abstract).  Combinator: obtain the two factors,
-- glue, thread source/target/IsDecompOn/origin-fixing straight through.
theorem build_non_letter0_equidecomp_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (g : Equidecomp E (E ≃ᵢ E)) (Sg : Finset (E ≃ᵢ E)),
      g.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      g.target = M ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨e₂, Sb, he₂s, he₂t, hd₂, h0₂⟩ :=
    b_letter_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨e₁, Sa, he₁s, he₁t, hd₁, h0₁⟩ :=
    absorb_empty_word_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨e, S, hes, het, hd, h0⟩ :=
    equidecomp_trans_glue_origin_fixing e₁ e₂ (by rw [he₁t, he₂s]) Sa Sb hd₁ hd₂ h0₁ h0₂
  exact ⟨e, S, by rw [hes, he₁s], by rw [het, he₂t], by rw [hes, he₁s] at hd ⊢; exact hd, h0⟩

-- Origin-fixing mirror of s11464: lift the F₂ 2-paradoxical split through φ, now ALSO

-- exposing the realizing Finsets Sf,Sg with every element fixing 0.  Orbit address
-- (rep,wrd) is cited inline from the proved orbit_address_of_free_action; the partition
-- of M by "first letter = generator 0?" pulls back to f.source/g.source.  Two new
-- origin-fixing builders reconstruct each piece together with its origin-fixing Finset
-- (letter-0 piece: Sf={1,φ(of 0)}; complement: Hilbert-hotel φ(of 1)-tower).
-- Combinator: disjointness + cover are the same {x∈M|P} ⊔ {x∈M|¬P} = M set algebra as
-- s11464; the IsDecompOn + origin-fixing fields thread straight through from the builders.
theorem paradoxical_of_free_isometry_action_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = M ∧
      f.target = M ∧
      g.target = M ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨rep, wrd, hx, hcoh⟩ := orbit_address_of_free_action φ M hinv hfree
  obtain ⟨f, Sf, hfs, hft, hfdec, hf0⟩ :=
    build_letter0_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨g, Sg, hgs, hgt, hgdec, hg0⟩ :=
    build_non_letter0_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  refine ⟨f, g, Sf, Sg, ?_, ?_, hft, hgt, hfdec, hgdec, hf0, hg0⟩
  · rw [hfs, hgs, Set.disjoint_left]
    rintro x ⟨_, hp⟩ ⟨_, hnp⟩
    exact hnp hp
  · rw [hfs, hgs]
    ext x
    simp only [Set.mem_union, Set.mem_setOf_eq]
    constructor
    · rintro (⟨hxM, _⟩ | ⟨hxM, _⟩) <;> exact hxM
    · intro hxM
      by_cases hp : (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0
      · exact Or.inl ⟨hxM, hp⟩
      · exact Or.inr ⟨hxM, hp⟩

-- Origin-fixing Hilbert-hotel absorption S² ≃ S²∖D, exposing origin-fixing decomp data.
-- Pick a rotation ρ fixing 0 with pairwise-disjoint orbits ρⁿ''D (proved sibling
-- exists_rotation_pairwise_disjoint_orbit_off_origin); build the piecewise hotel map
-- f = ρ on T = ⋃ₙ ρⁿ''D / id off T, g = ρ.symm on T / id off T, and assemble the
-- Equidecomp from the proved abstract bricks map_source/target_hilbert + left/right_inv_hilbert
-- (4 PartialEquiv laws) with hotel_shift (ρ''T = T∖D). Two strictly-simpler NEW sub-goals:
--   • hotel_subset_sphere — the orbit tower T stays on S² (ρⁿ fix 0, isometry preserves sphere);
--   • is_decomp_hilbert_origin_fixing — IsDecompOn with witness set {ρ,1} ALL FIXING 0, the
--     origin-fixing strengthening of the proved is_decomp_hilbert; reused for both h (via ρ)
--     and h.symm (via ρ.symm, which fixes 0 too).  Both sub-goals drop the equidecomp layer.
theorem sphere_hilbert_hotel_absorb_origin_fixing
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D) :
    ∃ (h : Equidecomp E (E ≃ᵢ E)) (Sh Sh' : Finset (E ≃ᵢ E)),
      h.source = Metric.sphere (0 : E) 1 ∧
      h.target = Metric.sphere (0 : E) 1 \ D ∧
      Equidecomp.IsDecompOn h.toFun h.source Sh ∧
      Equidecomp.IsDecompOn h.symm.toFun h.symm.source Sh' ∧
      (∀ s ∈ Sh, s 0 = 0) ∧ (∀ s ∈ Sh', s 0 = 0)  := by
  classical
  obtain ⟨ρ, hρ0, hdisj⟩ := exists_rotation_pairwise_disjoint_orbit_off_origin D hDc hD0
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hTdef
  set f : E → E := fun x => if x ∈ T then ρ x else x with hf_def
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hg_def
  have hf : ∀ x, x ∈ T → f x = ρ x := by intro x hx; rw [hf_def]; exact if_pos hx
  have hf' : ∀ x, x ∉ T → f x = x := by intro x hx; rw [hf_def]; exact if_neg hx
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := by intro y hy; rw [hg_def]; exact if_pos hy
  have hg' : ∀ y, y ∉ T → g y = y := by intro y hy; rw [hg_def]; exact if_neg hy
  have hshift : ρ '' T = T \ D := hotel_shift D ρ hdisj
  have hDT : D ⊆ T := fun x hx => Set.mem_iUnion.mpr ⟨0, by simpa using hx⟩
  have hTA : T ⊆ Metric.sphere (0 : E) 1 := hotel_subset_sphere D ρ hρ0 hDs
  have hms := map_source_hilbert (Metric.sphere (0 : E) 1) D T ρ f hf hf' hDT hTA hshift
  have hmt := map_target_hilbert (Metric.sphere (0 : E) 1) D T ρ g hg hg' hDT hTA hshift
  have hli := left_inv_hilbert (Metric.sphere (0 : E) 1) D T ρ f g hf hf' hg hg' hshift
  have hri := right_inv_hilbert (Metric.sphere (0 : E) 1) D T ρ f g hf hf' hg hg' hshift
  obtain ⟨Sh, hSh, hSh0⟩ :=
    is_decomp_hilbert_origin_fixing (Metric.sphere (0 : E) 1) T ρ hρ0 f hf hf'
  have hρ0' : ρ.symm 0 = 0 := by
    have := ρ.symm_apply_apply 0; rwa [hρ0] at this
  obtain ⟨Sh', hSh', hSh'0⟩ :=
    is_decomp_hilbert_origin_fixing (Metric.sphere (0 : E) 1 \ D) T ρ.symm hρ0' g hg hg'
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g (Metric.sphere (0 : E) 1)
      (Metric.sphere (0 : E) 1 \ D) hms hmt hli hri) ⟨Sh, hSh⟩, Sh, Sh', rfl, rfl,
    hSh, hSh', hSh0, hSh'0⟩

-- Origin-fixing strengthening of the Hausdorff→S²∖D paradox (mirror of s11459).
-- Geometric half is cited inline from PROVED bricks: exists_free_isometry_embedding (s11470)
-- gives an injective φ : F₂ ↪ (E≃ᵢE) with the EXTRA datum `∀ w, φ w 0 = 0` (every word is an
-- origin-fixing rotation) plus per-word finite fixed sets; fixed_free_action_off_countable
-- (s11471) takes its countable fixed-point union D ⊆ S² (0∉D), invariant + fixed-point-free off D.
-- The single sub-goal `paradoxical_of_free_isometry_action_origin_fixing` is the abstract lift:
-- it reuses the F₂ two-piece split (cf. s11464) but ADDITIONALLY exposes the realizing Finsets
-- Sf,Sg (shape {1, φ(of i)} / Hilbert-hotel tower of φ(of 1)-powers), all origin-fixing via hfix0.
-- Combinator: obtain D,φ + props inline, feed M := S²∖D and hfix0 to the lift.
-- Strictly simpler: the sub-goal drops ALL sphere/fixed-point geometry (abstract M).
theorem sphere_minus_fixed_paradoxical_origin_fixing :
    ∃ D : Set E, D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨φ, hinj, hfix0, hfin⟩ := exists_free_isometry_embedding
  obtain ⟨D, hcount, hsub, h0, hinv, hfree⟩ := fixed_free_action_off_countable φ hfix0 hfin
  exact ⟨D, hcount, hsub, h0,
    paradoxical_of_free_isometry_action_origin_fixing φ hinj
      (Metric.sphere (0 : E) 1 \ D) hinv hfree hfix0⟩

-- Mirror the proved non-origin-fixing absorption (s11458) but thread the origin-fixing
-- IsDecompOn data: (1) an origin-fixing Hilbert-hotel absorption equidecomp h : S² ≃ S²∖D
-- (rotation ρ and ρ⁻¹ fix 0, so both h and h.symm have origin-fixing decomp sets), then
-- (2) a generic transfer that carries a B-paradox with origin-fixing data to A preserving it.
theorem absorb_countable_paradoxical_origin_fixing
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨h, Sh, Sh', hsrc, htgt, hdec_h, hdec_h', h0h, h0h'⟩ :=
    sphere_hilbert_hotel_absorb_origin_fixing D hDc hDs hD0
  exact paradoxical_transfer_along_equidecomp_origin_fixing
    (Metric.sphere (0 : E) 1) (Metric.sphere (0 : E) 1 \ D)
    h Sh Sh' hsrc htgt hdec_h hdec_h' h0h h0h' hp

-- Strengthen the proved sphere paradox (s11455) with origin-fixing witnessing data,
-- mirroring its two-layer structure but threading the IsDecompOn sets Sf/Sg whose
-- isometries all fix 0 (the F₂↪SO(3) generators and the absorption rotation are rotations).
-- (1) sphere_minus_fixed_paradoxical_origin_fixing: the free-action paradox of S²∖D with
--     origin-fixing decomposition sets — drops the absorption layer.
-- (2) absorb_countable_paradoxical_origin_fixing: transfer the S²∖D paradox to S² preserving
--     the origin-fixing data — generic Hilbert-hotel absorption, no free-group machinery.
-- Combinator: obtain D + the strengthened paradox from (1), feed to (2).
theorem sphere_paradoxical_origin_fixing :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨D, hDc, hDs, hD0, hp⟩ := sphere_minus_fixed_paradoxical_origin_fixing
  exact absorb_countable_paradoxical_origin_fixing D hDc hDs hD0 hp

-- Absorb the single point {0} into closedBall by a Hilbert hotel run along an
-- off-origin rotation whose 0-orbit is injective and stays inside the ball.
-- (1) bounded_injective_rotation_orbit: existence of such ρ (orbit ⊆ ball + pairwise-disjoint).
-- (2) relaxed_hilbert_hotel: the `T ⊆ A` variant of the Hilbert-hotel equidecomposition,
--     dropping the too-strong `∀ x∈A, ρ x∈A` invariance (which fails for off-origin ρ since
--     ρ maps closedBall 0 1 to closedBall (ρ 0) 1).  Instantiate (2) at A = closedBall, D = {0}.
theorem ball_origin_absorb_equidecomp :
    ∃ e : Equidecomp E (E ≃ᵢ E),
      e.source = Metric.closedBall (0 : E) 1 ∧
      e.target = Metric.closedBall (0 : E) 1 \ {0}  := by
  obtain ⟨ρ, hTA, hdisj⟩ := bounded_injective_rotation_orbit
  exact relaxed_hilbert_hotel (Metric.closedBall (0 : E) 1) ({0} : Set E) ρ
    (by simp) hTA hdisj

-- Absorb the origin via a Hilbert-hotel equidecomposition closedBall ≃ closedBall∖{0}
-- (off-origin rotation with injective 0-orbit inside the ball), then transport the
-- punctured-ball paradox (h) up to the full ball via paradoxical_transfer_along_equidecomp.
theorem ball_paradoxical_of_punctured
    (h : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
      f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
      g.target = Metric.closedBall (0 : E) 1 \ {0}) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 ∧
      f.target = Metric.closedBall (0 : E) 1 ∧
      g.target = Metric.closedBall (0 : E) 1  := by
  obtain ⟨e, hsrc, htgt⟩ := ball_origin_absorb_equidecomp
  exact paradoxical_transfer_along_equidecomp
    (Metric.closedBall (0 : E) 1) (Metric.closedBall (0 : E) 1 \ {0}) e hsrc htgt h

-- Cone-lift transport: lift each sphere Equidecomp piece radially to the punctured ball.
-- Each piece's decomposition isometries fix 0, hence commute with radial scaling, so the
-- map y ↦ ‖y‖•(piece(‖y‖⁻¹•y)) extends each piece to the cone of its source. The cone of
-- the unit sphere is the punctured ball (cone_over_sphere_eq_punctured_ball / s11488), so
-- coning the two sphere pieces reassembles the punctured-ball paradox.
-- (1) cone_lift_equidecomp: the abstract single-piece cone functor (origin-fixing ⇒ radial).
-- (2) cone_distrib_union / (3) cone_preserves_disjoint: set-algebra of the cone over a sphere.
theorem punctured_ball_of_origin_fixing_sphere
    (hsph : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
      f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
      g.target = Metric.closedBall (0 : E) 1 \ {0}  := by
  obtain ⟨f, g, Sf, Sg, hdisj, hunion, hftgt, hgtgt, hfdec, hgdec, hf0, hg0⟩ := hsph
  have hfsrc_sub : f.source ⊆ Metric.sphere (0 : E) 1 := by
    rw [← hunion]; exact Set.subset_union_left
  have hgsrc_sub : g.source ⊆ Metric.sphere (0 : E) 1 := by
    rw [← hunion]; exact Set.subset_union_right
  obtain ⟨F, hFsrc, hFtgt⟩ :=
    cone_lift_equidecomp f Sf hfdec hf0 hfsrc_sub hftgt.subset
  obtain ⟨G, hGsrc, hGtgt⟩ :=
    cone_lift_equidecomp g Sg hgdec hg0 hgsrc_sub hgtgt.subset
  refine ⟨F, G, ?_, ?_, ?_, ?_⟩
  · rw [hFsrc, hGsrc]
    exact cone_preserves_disjoint f.source g.source hfsrc_sub hgsrc_sub hdisj
  · rw [hFsrc, hGsrc, ← cone_distrib_union f.source g.source, hunion]
    exact cone_over_sphere_eq_punctured_ball
  · rw [hFtgt, hftgt]; exact cone_over_sphere_eq_punctured_ball
  · rw [hGtgt, hgtgt]; exact cone_over_sphere_eq_punctured_ball

-- Cone-lift transport. The punctured closed ball is exactly the radial cone over the unit
-- sphere (cone_over_sphere_eq_punctured_ball / s11488), and an origin-fixing isometry commutes
-- with radial scaling: g (r•x) = r•(g x) (isometry_fixing_origin_smul_comm / s11475). Hence a
-- sphere paradox whose witnessing isometries all fix 0 lifts ray-by-ray (y ↦ ‖y‖•(g (‖y‖⁻¹•y)))
-- to a paradox of closedBall\{0}.
-- (1) sphere_paradoxical_origin_fixing: the proved sphere paradox, strengthened with the extra
--     data that each piece is realized by a finite set of origin-fixing isometries (SO(3)
--     rotations do fix 0). Sphere region only — strictly simpler than the solid-ball assembly.
-- (2) punctured_ball_of_origin_fixing_sphere: takes (1) as a hypothesis and performs the cone
--     lift + reassembly; never re-derives the paradox, so it is a pure transport step.
theorem punctured_ball_paradoxical : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
    Disjoint f.source g.source ∧
    f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
    f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
    g.target = Metric.closedBall (0 : E) 1 \ {0}  := by
  exact punctured_ball_of_origin_fixing_sphere sphere_paradoxical_origin_fixing

-- Decompose the solid-ball paradox into: (1) the punctured ball closedBall\{0}
-- is paradoxical (radial cone lift of the proved sphere paradox), and
-- (2) single-point (origin) absorption pulls the punctured-ball paradox up to
-- the full closed ball. Glue: feed (1)'s conclusion as (2)'s hypothesis.
theorem main : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
  Disjoint f.source g.source ∧
  f.source ∪ g.source = Metric.closedBall (0 : E) 1 ∧
  f.target = Metric.closedBall (0 : E) 1 ∧
  g.target = Metric.closedBall (0 : E) 1  := by
  have h_punctured := punctured_ball_paradoxical
  exact ball_paradoxical_of_punctured h_punctured

end Library.Geometry.BanachTarski.Equidecomp
