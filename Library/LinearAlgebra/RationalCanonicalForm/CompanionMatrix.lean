import Mathlib

namespace Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix

def companionMatrix {K : Type*} [Field K] (f : Polynomial K) :
    Matrix (Fin f.natDegree) (Fin f.natDegree) K :=
  Matrix.of fun i j =>
    if (i : ℕ) = (j : ℕ) + 1 then 1
    else if (j : ℕ) = f.natDegree - 1 then -f.coeff (i : ℕ)
    else 0

-- xpow_modbymonic_lt: X^m %ₘ f = X^m when m < natDegree f (monic f),
-- via modByMonic_eq_self_iff + degree_X_pow + degree_eq_natDegree.
theorem xpow_modbymonic_lt {K : Type*} [Field K] {f : Polynomial K} (hf : f.Monic)
    {m : ℕ} (hm : m < f.natDegree) :
    Polynomial.X ^ m %ₘ f = Polynomial.X ^ m := by
  rw [Polynomial.modByMonic_eq_self_iff hf]
  rw [Polynomial.degree_X_pow]
  rw [Polynomial.degree_eq_natDegree hf.ne_zero]; exact_mod_cast hm

-- entry_kind: Builder
-- xpow_modbymonic_self: X^(natDegree f) %ₘ f = X^(natDegree f) - f for monic f,
-- via div_modByMonic_unique with quotient 1 and remainder X^n - f.
theorem xpow_modbymonic_self {K : Type*} [Field K] {f : Polynomial K} (hf : f.Monic) :
    Polynomial.X ^ f.natDegree %ₘ f = Polynomial.X ^ f.natDegree - f := by
  have hfdeg : f.degree = f.natDegree := Polynomial.degree_eq_natDegree hf.ne_zero
  have hdeg : (Polynomial.X (R := K) ^ f.natDegree).degree = f.degree := by
    rw [Polynomial.degree_X_pow, hfdeg]
  have hlc : (Polynomial.X (R := K) ^ f.natDegree).leadingCoeff = f.leadingCoeff := by
    rw [Polynomial.leadingCoeff_X_pow, hf.leadingCoeff]
  exact (Polynomial.div_modByMonic_unique 1 (Polynomial.X ^ f.natDegree - f) hf
    ⟨by ring, hdeg ▸ Polynomial.degree_sub_lt hdeg
        (pow_ne_zero f.natDegree (Polynomial.X_ne_zero (R := K))) hlc⟩).2

-- entry_kind: Builder
-- repr_mulleft_basis_eq_modbymonic: the powerBasis' repr of mulLeft(root f)(basis j) equals
-- (X^(j+1) %ₘ f).coeff i, using powerBasisAux'_repr_apply_to_fun + modByMonicHom_mk
theorem repr_mulleft_basis_eq_modbymonic {K : Type*} [Field K] {f : Polynomial K}
    (hf : f.Monic) (i j : Fin f.natDegree) :
    (AdjoinRoot.powerBasis' hf).basis.repr
      (LinearMap.mulLeft K (AdjoinRoot.root f) ((AdjoinRoot.powerBasis' hf).basis j)) i
      = (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff i := by
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

-- Entrywise computation of `(X^(j+1) %ₘ f).coeff i`, split on whether the
-- exponent `j+1` is below `natDegree f` (low) or equals it (high).
-- Low: `X^(j+1) %ₘ f = X^(j+1)` (xpow_modbymonic_lt), coeff is `if i = j+1`.
-- High: `X^n %ₘ f = X^n - f` (xpow_modbymonic_self); coeff i = -f.coeff i.
-- Both reduce to `companionMatrix` via its definition + Fin bounds (omega).
theorem modbymonic_coeff_eq_companion {K : Type*} [Field K] {f : Polynomial K}
    (hf : f.Monic) (i j : Fin f.natDegree) :
    (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff i = companionMatrix f i j  := by
  by_cases hj : (j : ℕ) + 1 < f.natDegree
  · -- low case
    have hlt : Polynomial.X ^ ((j : ℕ) + 1) %ₘ f = Polynomial.X ^ ((j : ℕ) + 1) :=
      xpow_modbymonic_lt hf hj
    have hjn : (j : ℕ) ≠ f.natDegree - 1 := by omega
    rw [hlt, Polynomial.coeff_X_pow, companionMatrix]
    simp only [Matrix.of_apply]
    rw [if_neg hjn]
  · -- high case
    have hjeq : (j : ℕ) + 1 = f.natDegree := by have := j.is_lt; omega
    have hself : Polynomial.X ^ ((j : ℕ) + 1) %ₘ f
        = Polynomial.X ^ ((j : ℕ) + 1) - f := by
      rw [hjeq]; exact xpow_modbymonic_self hf
    have hjn : (j : ℕ) = f.natDegree - 1 := by omega
    have hin : (i : ℕ) ≠ (j : ℕ) + 1 := by have := i.is_lt; omega
    rw [hself, Polynomial.coeff_sub, Polynomial.coeff_X_pow, companionMatrix]
    simp only [Matrix.of_apply]
    rw [if_neg hin, if_neg hin, if_pos hjn]
    ring

-- Entrywise: rewrite `toMatrix … i j` to the power-basis repr coordinate, transport
-- that coordinate to the polynomial world `(X^(j+1) %ₘ f).coeff i` (h_repr_to_poly),
-- then compute that coefficient against the companion matrix entry (h_modByMonic_eq_companion).
theorem companion_matrix_eq_tomatrix_mulx {K : Type*} [Field K] {f : Polynomial K}
    (hf : f.Monic) :
    LinearMap.toMatrix (AdjoinRoot.powerBasis' hf).basis (AdjoinRoot.powerBasis' hf).basis
        (LinearMap.mulLeft K (AdjoinRoot.root f))
      = companionMatrix f  := by
  ext i j
  have h_repr_to_poly := repr_mulleft_basis_eq_modbymonic hf i j
  have h_modByMonic_eq_companion := modbymonic_coeff_eq_companion hf i j
  rw [LinearMap.toMatrix_apply, h_repr_to_poly, h_modByMonic_eq_companion]

-- block_companion: toMatrix of mulLeft-root in powerBasis' equals companionMatrix;
-- direct application of the already-proved companion_matrix_eq_tomatrix_mulx theorem (variable rename only).
theorem block_companion {K : Type*} [Field K] {g : Polynomial K} (hg : g.Monic) :
    LinearMap.toMatrix (AdjoinRoot.powerBasis' hg).basis (AdjoinRoot.powerBasis' hg).basis
        (LinearMap.mulLeft K (AdjoinRoot.root g))
      = companionMatrix g := companion_matrix_eq_tomatrix_mulx hg

end Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix
