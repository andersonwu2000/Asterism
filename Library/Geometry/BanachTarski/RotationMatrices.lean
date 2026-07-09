import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Library.Geometry.BanachTarski.Defs
import Library.Geometry.BanachTarski.OrthogonalMatrices

/-!
# Rotation matrices for the Banach–Tarski construction

This file establishes algebraic and isometric properties of the two families of
rotation matrices used in the Banach–Tarski paradox: z-axis rotations and x-axis
rotations acting on $\mathbb{R}^3$ (represented as the Euclidean space `E`).

## Main statements

- `z_rotation_matrix_mul_eq_add` : the product of two z-rotation matrices by angles `θ` and `φ`
  equals the z-rotation matrix by `θ + φ`.
- `z_rotation_block_orthogonal` : every z-rotation matrix is orthogonal.
- `z_rotation_matrix_pow` : the `n`-th power of the z-rotation matrix by `θ` equals the
  z-rotation matrix by `n * θ`.
- `isometry_pow_realizes_matrix_pow` : if an isometry `e` acts as a matrix `A`, then `e ^ n`
  acts as `A ^ n`.
- `z_rotation_isometry_family_realizes_matrix` : there exists a family `R : ℝ → E ≃ᵢ E` of
  isometries that realises the z-rotation matrices and satisfies `(R θ) ^ n = R (n * θ)`.
- `x_rotation_block_orthogonal` : every x-rotation matrix is orthogonal.
- `x_rot_fixes_first_coord` / `x_rot_second_coord` : coordinate formulas for the x-rotation
  isometry family.
-/

open Library.Geometry.BanachTarski.Defs
open Library.Geometry.BanachTarski.OrthogonalMatrices

namespace Library.Geometry.BanachTarski.RotationMatrices

/-- The z-rotation matrices satisfy the addition formula: the product of the rotation matrices
by angles `θ` and `φ` equals the rotation matrix by `θ + φ`. -/
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

/-- The z-rotation matrix by angle `θ` is orthogonal: its transpose times itself equals
the identity matrix. -/
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

/-- The `n`-th power of the z-rotation matrix by angle `θ` equals the z-rotation matrix
by `n * θ`. Proved by induction using `z_rotation_matrix_mul_eq_add`. -/
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

/-- If an isometry `e` of `E` acts as multiplication by a matrix `A` (i.e., `e x = A • x`
for all `x`), then `e ^ n` acts as multiplication by `A ^ n`. -/
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

/-- There exists a measurable family `R : ℝ → E ≃ᵢ E` of isometries that realises the
z-rotation matrices: `R θ` fixes the origin, satisfies `(R θ) ^ n = R (n * θ)`, and
acts on `E` as the block rotation matrix
$$\begin{pmatrix} \cos\theta & -\sin\theta & 0 \\ \sin\theta & \cos\theta & 0 \\ 0 & 0 & 1
\end{pmatrix}.$$
-/
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

/-- The x-rotation matrix by angle `φ` is orthogonal: its transpose times itself equals
the identity matrix. -/
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

/-- An x-rotation isometry family `Q` preserves the first coordinate: `(Q φ p) 0 = p 0`
for all angles `φ` and points `p : E`. -/
theorem x_rot_fixes_first_coord
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) :
    ∀ (φ : ℝ), (Q φ p) 0 = p 0 := by aesop

/-- An x-rotation isometry family `Q` transforms the second coordinate by
`(Q φ p) 1 = cos φ * p 1 - sin φ * p 2`. -/
theorem x_rot_second_coord
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) :
    ∀ (φ : ℝ), (Q φ p) 1 = Real.cos φ * p 1 - Real.sin φ * p 2 := by aesop

end Library.Geometry.BanachTarski.RotationMatrices
