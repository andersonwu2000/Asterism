import Mathlib.Algebra.Module.LinearMap.Defs
import Mathlib.Algebra.Polynomial.Basic
import Mathlib.Algebra.Polynomial.Degree.Defs
import Mathlib.Algebra.Polynomial.Div
import Mathlib.Algebra.Polynomial.FieldDivision
import Mathlib.Data.Matrix.Basic
import Mathlib.LinearAlgebra.Matrix.Basis
import Mathlib.RingTheory.AdjoinRoot

/-!
# Companion Matrix for Rational Canonical Form

This file defines the companion matrix of a polynomial over a field and proves that it equals
the matrix of multiplication-by-root in the power basis of the adjoin-root algebra.

## Main definitions

- `companionMatrix`: the companion matrix of a polynomial `f`, with `1`s on the subdiagonal and
  negated coefficients of `f` in the last column.

## Main statements

- `xpow_modByMonic_lt`: `X ^ m %ₘ f = X ^ m` when `m < natDegree f` and `f` is monic.
- `xpow_modByMonic_self`: `X ^ natDegree f %ₘ f = X ^ natDegree f - f` for monic `f`.
- `repr_mulLeft_basis_eq_modByMonic`: the power-basis coordinate of `root f ^ (j+1)` equals the
  `i`-th coefficient of `X ^ (j+1) %ₘ f`.
- `modByMonic_coeff_eq_companion`: entrywise, `(X ^ (j+1) %ₘ f).coeff i = companionMatrix f i j`.
- `companion_matrix_eq_toMatrix_mulLeft`: the matrix of `mulLeft (root f)` in the power basis
  equals `companionMatrix f`.
- `block_companion`: a restatement of `companion_matrix_eq_toMatrix_mulLeft` for block
  decompositions.
-/

namespace Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix

variable {K : Type*} [Field K]

/-- The companion matrix of a polynomial `f` of degree `n`: the `n × n` matrix with `1`s on
the subdiagonal and the negated coefficients of `f` in the last column. -/
def companionMatrix (f : Polynomial K) : Matrix (Fin f.natDegree) (Fin f.natDegree) K :=
  Matrix.of fun i j =>
    if (i : ℕ) = (j : ℕ) + 1 then 1
    else if (j : ℕ) = f.natDegree - 1 then -f.coeff (i : ℕ)
    else 0

/-- When `m < natDegree f`, `X ^ m` is already reduced modulo the monic polynomial `f`. -/
theorem xpow_modByMonic_lt {f : Polynomial K} (hf : f.Monic) {m : ℕ} (hm : m < f.natDegree) :
    Polynomial.X ^ m %ₘ f = Polynomial.X ^ m := by
  rw [Polynomial.modByMonic_eq_self_iff hf, Polynomial.degree_X_pow,
    Polynomial.degree_eq_natDegree hf.ne_zero]
  exact_mod_cast hm

/-- `X ^ natDegree f` reduced modulo the monic polynomial `f` equals `X ^ natDegree f - f`. -/
theorem xpow_modByMonic_self {f : Polynomial K} (hf : f.Monic) :
    Polynomial.X ^ f.natDegree %ₘ f = Polynomial.X ^ f.natDegree - f := by
  have hfdeg : f.degree = f.natDegree := Polynomial.degree_eq_natDegree hf.ne_zero
  have hdeg : (Polynomial.X (R := K) ^ f.natDegree).degree = f.degree := by
    rw [Polynomial.degree_X_pow, hfdeg]
  have hlc : (Polynomial.X (R := K) ^ f.natDegree).leadingCoeff = f.leadingCoeff := by
    rw [Polynomial.leadingCoeff_X_pow, hf.leadingCoeff]
  exact (Polynomial.div_modByMonic_unique 1 (Polynomial.X ^ f.natDegree - f) hf
    ⟨by ring, hdeg ▸ Polynomial.degree_sub_lt hdeg
        (pow_ne_zero f.natDegree (Polynomial.X_ne_zero (R := K))) hlc⟩).2

/-- The `i`-th power-basis coordinate of `mulLeft (root f) (basis j)` equals the `i`-th
coefficient of `X ^ (j + 1) %ₘ f`. -/
theorem repr_mulLeft_basis_eq_modByMonic {f : Polynomial K} (hf : f.Monic)
    (i j : Fin f.natDegree) :
    (AdjoinRoot.powerBasis' hf).basis.repr
      (LinearMap.mulLeft K (AdjoinRoot.root f) ((AdjoinRoot.powerBasis' hf).basis j)) i =
      (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff i := by
  have h1 : (AdjoinRoot.powerBasis' hf).basis j = AdjoinRoot.root f ^ (j : ℕ) :=
    (AdjoinRoot.powerBasis' hf).basis_eq_pow j
  rw [h1, LinearMap.mulLeft_apply]
  have h2 : AdjoinRoot.root f * AdjoinRoot.root f ^ (j : ℕ) =
      AdjoinRoot.root f ^ ((j : ℕ) + 1) := by ring
  rw [h2]
  rw [show (AdjoinRoot.powerBasis' hf).basis.repr = (AdjoinRoot.powerBasisAux' hf).repr from rfl]
  change (AdjoinRoot.modByMonicHom hf (AdjoinRoot.root f ^ ((j : ℕ) + 1))).coeff ↑i =
      (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff ↑i
  have h3 : AdjoinRoot.root f ^ ((j : ℕ) + 1) =
      AdjoinRoot.mk f (Polynomial.X ^ ((j : ℕ) + 1)) := by
    rw [← AdjoinRoot.mk_X (f := f), ← map_pow]
  rw [h3, AdjoinRoot.modByMonicHom_mk]

/-- Entrywise, `(X ^ (j+1) %ₘ f).coeff i` equals the `(i, j)` entry of `companionMatrix f`.
Proved by splitting on whether `j + 1 < natDegree f` (low case, use `xpow_modByMonic_lt`) or
`j + 1 = natDegree f` (high case, use `xpow_modByMonic_self`). -/
theorem modByMonic_coeff_eq_companion {f : Polynomial K} (hf : f.Monic)
    (i j : Fin f.natDegree) :
    (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff i = companionMatrix f i j := by
  by_cases hj : (j : ℕ) + 1 < f.natDegree
  · have hlt : Polynomial.X ^ ((j : ℕ) + 1) %ₘ f = Polynomial.X ^ ((j : ℕ) + 1) :=
      xpow_modByMonic_lt hf hj
    have hjn : (j : ℕ) ≠ f.natDegree - 1 := by omega
    rw [hlt, Polynomial.coeff_X_pow, companionMatrix]
    simp only [Matrix.of_apply]
    rw [if_neg hjn]
  · have hjeq : (j : ℕ) + 1 = f.natDegree := by have := j.is_lt; omega
    have hself : Polynomial.X ^ ((j : ℕ) + 1) %ₘ f = Polynomial.X ^ ((j : ℕ) + 1) - f := by
      rw [hjeq]; exact xpow_modByMonic_self hf
    have hjn : (j : ℕ) = f.natDegree - 1 := by omega
    have hin : (i : ℕ) ≠ (j : ℕ) + 1 := by have := i.is_lt; omega
    rw [hself, Polynomial.coeff_sub, Polynomial.coeff_X_pow, companionMatrix]
    simp only [Matrix.of_apply]
    rw [if_neg hin, if_neg hin, if_pos hjn]
    ring

/-- **Companion matrix**: the matrix of `mulLeft (root f)` in the power basis of `AdjoinRoot f`
equals `companionMatrix f`. -/
theorem companion_matrix_eq_toMatrix_mulLeft {f : Polynomial K} (hf : f.Monic) :
    LinearMap.toMatrix (AdjoinRoot.powerBasis' hf).basis (AdjoinRoot.powerBasis' hf).basis
        (LinearMap.mulLeft K (AdjoinRoot.root f)) =
      companionMatrix f := by
  ext i j
  have h_repr_to_poly := repr_mulLeft_basis_eq_modByMonic hf i j
  have h_modByMonic_eq_companion := modByMonic_coeff_eq_companion hf i j
  rw [LinearMap.toMatrix_apply, h_repr_to_poly, h_modByMonic_eq_companion]

/-- Alias of `companion_matrix_eq_toMatrix_mulLeft` for use in block decompositions. -/
theorem block_companion {g : Polynomial K} (hg : g.Monic) :
    LinearMap.toMatrix (AdjoinRoot.powerBasis' hg).basis (AdjoinRoot.powerBasis' hg).basis
        (LinearMap.mulLeft K (AdjoinRoot.root g)) =
      companionMatrix g := companion_matrix_eq_toMatrix_mulLeft hg

end Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix
