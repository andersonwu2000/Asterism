import Library.LinearAlgebra.JordanForm.Defs
import Mathlib

/-!
# Block enumeration for Jordan normal form indices

This file constructs a contiguous-block enumeration of the sigma fintype `(μ : K) × Fin (n μ)`,
showing that there exists an equivalence from `Fin (∑ n)` (or `Fin (finrank V)`) to the sigma
type under which consecutive flat indices within the same block correspond exactly to consecutive
fiber indices. The main result, `jordan_block_enumeration`, strips away all linear-algebra
hypotheses and reduces to pure index combinatorics.
-/

open Library.LinearAlgebra.JordanForm.Defs

namespace Library.LinearAlgebra.JordanForm.BlockEnum

/-- The lexicographic enumeration `finSigmaFinEquiv.symm` on `Fin (∑ i, ν i)` admits prefix-sum
offsets: for each `p`, the flat value equals the offset of its block plus its within-block index. -/
theorem fin_offset_block_enum {m : ℕ} (ν : Fin m → ℕ) :
    ∃ (e : Fin (∑ i, ν i) ≃ Σ i : Fin m, Fin (ν i)) (o : Fin m → ℕ),
      ∀ p : Fin (∑ i, ν i), (p : ℕ) = o (e p).1 + ((e p).2 : ℕ) := by
  refine ⟨finSigmaFinEquiv.symm, fun i => ∑ j : Fin i, ν (Fin.castLE i.isLt.le j), fun p => ?_⟩
  have h := finSigmaFinEquiv_apply (finSigmaFinEquiv.symm p)
  simp [Equiv.apply_symm_apply] at h
  exact h

section
variable {ι : Type*} [Fintype ι] (k : ι → ℕ)

/-- Transport a `Fin m`-indexed block enumeration with offsets to an arbitrary `Fintype ι` index
via an equivalence `σ : ι ≃ Fin m` and a block-size compatibility hypothesis. -/
theorem offset_enum_transport {m : ℕ} (σ : ι ≃ Fin m)
    (ν : Fin m → ℕ) (hν : ∀ i, ν i = k (σ.symm i))
    (e : Fin (∑ i, ν i) ≃ Σ i : Fin m, Fin (ν i)) (o : Fin m → ℕ)
    (he : ∀ p : Fin (∑ i, ν i), (p : ℕ) = o (e p).1 + ((e p).2 : ℕ)) :
    ∃ (e' : Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s)) (o' : ι → ℕ),
      ∀ p : Fin (∑ s, k s), (p : ℕ) = o' (e' p).1 + ((e' p).2 : ℕ) := by
  have hsum : (∑ s, k s) = ∑ i, ν i := by
    rw [← Equiv.sum_comp σ.symm k]
    exact Finset.sum_congr rfl (fun i _ => (hν i).symm)
  refine ⟨(finCongr hsum).trans (e.trans (Equiv.sigmaCongr σ.symm (fun i => finCongr (hν i)))),
          fun s => o (σ s), fun p => ?_⟩
  have key := he (finCongr hsum p)
  simp only [Equiv.trans_apply, Equiv.sigmaCongr, Equiv.sigmaCongrRight_apply,
    Equiv.sigmaCongrLeft_apply, finCongr_apply, Fin.val_cast] at key ⊢
  rw [Equiv.apply_symm_apply]
  exact key

-- Reduce arbitrary Fintype index `ι` to `Fin (card ι)` via `Fintype.equivFin`, build the
-- lexicographic block enumeration there (`fin_offset_block_enum`), then transport the
-- enumeration + offsets back along the index equiv (`offset_enum_transport`).
/-- For any `Fintype ι` and block-size function `k : ι → ℕ`, there exists an equivalence
`Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s)` with per-block offsets decomposing each flat index. -/
theorem offset_block_enum :
    ∃ (e : Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s)) (o : ι → ℕ),
      ∀ p : Fin (∑ s, k s), (p : ℕ) = o (e p).1 + ((e p).2 : ℕ) := by
  obtain ⟨e, o, he⟩ := fin_offset_block_enum (fun i => k ((Fintype.equivFin ι).symm i))
  exact offset_enum_transport k (Fintype.equivFin ι)
    (fun i => k ((Fintype.equivFin ι).symm i)) (fun _ => rfl) e o he

-- Reduce the within-block consecutive-index iff to a coordinate formula.
-- Sub-goal `offset_block_enum` supplies an enumeration `e` plus per-block
-- offsets `o` with `(p : ℕ) = o (e p).1 + (e p).2`; on a shared block the
-- offsets cancel, so the consecutive-index equivalence is pure `omega`.
/-- There exists an equivalence `Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s)` such that for two indices
in the same block, consecutive fiber indices correspond exactly to consecutive flat indices. -/
theorem block_enum_consecutive :
    ∃ e : Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s),
      ∀ p q : Fin (∑ s, k s),
        (e p).1 = (e q).1 →
          (((e p).2 : ℕ) + 1 = ((e q).2 : ℕ) ↔ (p : ℕ) + 1 = (q : ℕ)) := by
  have h_enum := offset_block_enum k
  obtain ⟨e, o, he⟩ := h_enum
  refine ⟨e, fun p q hpq => ?_⟩
  have hp := he p
  have hq := he q
  have ho : o (e p).fst = o (e q).fst := by rw [hpq]
  omega

end

-- Reduce to the concrete lexicographic enumeration `finSigmaFinEquiv` (offset depends
-- only on the block index). `e` transports `finSigmaFinEquiv.symm` across the cardinality
-- bridge `card = ∑ ν`. The consecutiveness iff for same-block elements is the sub-goal
-- `sigma_enum_consecutive`; `finCongr` is value-preserving so the flat index threads through.
/-- For a `Fin m`-indexed sigma type, the canonical enumeration of `Fin (card ((i : Fin m) × Fin (ν i)))`
has the property that same-block elements are consecutive in the flat order if and only if they are
consecutive in the fiber. -/
theorem fin_base_block_enum {m : ℕ} (ν : Fin m → ℕ) :
    ∃ e : Fin (Fintype.card ((i : Fin m) × Fin (ν i))) ≃ ((i : Fin m) × Fin (ν i)),
      ∀ p q : Fin (Fintype.card ((i : Fin m) × Fin (ν i))), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ))) := by
  have hcard : Fintype.card ((i : Fin m) × Fin (ν i)) = ∑ i, ν i := by
    simp [Fintype.card_sigma]
  obtain ⟨e, he⟩ := block_enum_consecutive ν
  refine ⟨(finCongr hcard).trans e, fun p q hpq => ?_⟩
  simp only [Equiv.trans_apply] at hpq ⊢
  simpa [finCongr_apply] using he _ _ hpq

section
variable {K : Type*}

-- Direct construction:
-- Step 1: derive `Fintype {μ // 0 < n μ}` from the ambient sigma Fintype via the
-- injection `μ ↦ ⟨μ, 0⟩`; take `m := Fintype.card …`, `e := (Fintype.equivFin …).symm`.
-- Step 2: build `φ` as `sigmaCongrLeft e ≫ sigmaSubtypeEquivOfSubset` — both equivs
-- leave the fiber index alone (so `.2`-preservation is `rfl`), and fiber equality
-- reduces to `e`-injectivity via `Subtype.coe_inj` + `EmbeddingLike.apply_eq_iff_eq`.
/-- Given a sigma type `(μ : K) × Fin (n μ)` with a `Fintype` instance, there exist `m : ℕ`,
`ν : Fin m → ℕ`, and an equivalence `φ : (i : Fin m) × Fin (ν i) ≃ (μ : K) × Fin (n μ)` that
preserves fiber values and respects block membership. -/
theorem reduce_to_fin_base (n : K → ℕ) [Fintype ((μ : K) × Fin (n μ))] :
    ∃ (m : ℕ) (ν : Fin m → ℕ)
      (φ : ((i : Fin m) × Fin (ν i)) ≃ ((μ : K) × Fin (n μ))),
      (∀ x, ((φ x).2 : ℕ) = (x.2 : ℕ)) ∧ (∀ x y, (φ x).1 = (φ y).1 ↔ x.1 = y.1) := by
  haveI : Fintype {μ : K // 0 < n μ} :=
    Fintype.ofInjective
      (fun x : {μ : K // 0 < n μ} => (⟨x.1, ⟨0, x.2⟩⟩ : (μ : K) × Fin (n μ)))
      (fun ⟨_, _⟩ ⟨_, _⟩ h => by
        simp only [Sigma.mk.inj_iff] at h
        exact Subtype.ext h.1)
  refine ⟨Fintype.card {μ : K // 0 < n μ},
    fun i => n ((Fintype.equivFin {μ : K // 0 < n μ}).symm i).val,
    (Equiv.sigmaCongrLeft (Fintype.equivFin {μ : K // 0 < n μ}).symm).trans
      (Equiv.sigmaSubtypeEquivOfSubset (fun μ => Fin (n μ)) (fun μ => 0 < n μ)
        (fun _ x => x.pos)), ?_, ?_⟩
  · rintro ⟨i, j⟩
    rfl
  · rintro ⟨i, j⟩ ⟨i', j'⟩
    change (↑((Fintype.equivFin _).symm i) : K) = ↑((Fintype.equivFin _).symm i') ↔ i = i'
    rw [Subtype.coe_inj, EmbeddingLike.apply_eq_iff_eq]

-- Reduce to a `Fin m`-indexed base: `reduce_to_fin_base` enumerates the (finite) support
-- `{μ // 0 < n μ}` as `Fin m`, giving an equiv `φ` that preserves both fiber membership
-- (`(φ x).1 = (φ y).1 ↔ x.1 = y.1`) and the second-coordinate value (`(φ x).2 = x.2`).
-- `fin_base_block_enum` supplies the contiguous-block enumeration over the `Fin m` base
-- (provable from `finSigmaFinEquiv`, whose offset depends only on the block index).
-- The two combine: transport the `Fin m`-base enumeration across `φ`, then transfer the
-- consecutiveness iff through the value/fiber-preservation facts.
/-- For a `K`-indexed sigma fintype `(μ : K) × Fin (n μ)`, there exists an enumeration of
`Fin (card ((μ : K) × Fin (n μ)))` such that same-block elements are consecutive in the flat
order if and only if they are consecutive in the fiber. -/
theorem block_enum_of_card
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))] :
    ∃ e : Fin (Fintype.card ((μ : K) × Fin (n μ))) ≃ ((μ : K) × Fin (n μ)),
      ∀ p q : Fin (Fintype.card ((μ : K) × Fin (n μ))), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ))) := by
  have h_reduce := reduce_to_fin_base n
  obtain ⟨m, ν, φ, hφ2, hφ1⟩ := h_reduce
  have h_enum := fin_base_block_enum ν
  obtain ⟨e0, he0⟩ := h_enum
  have hcard : Fintype.card ((μ : K) × Fin (n μ)) = Fintype.card ((i : Fin m) × Fin (ν i)) :=
    (Fintype.card_congr φ).symm
  refine ⟨(finCongr hcard).trans (e0.trans φ), ?_⟩
  intro p q hpq
  simp only [Equiv.trans_apply, finCongr_apply] at hpq ⊢
  rw [hφ1] at hpq
  rw [hφ2, hφ2, he0 _ _ hpq]
  simp

-- Drop all linear-algebra context: the goal is pure index combinatorics on the sigma fintype.
-- Basis `b` gives `finrank K V = card ((μ:K) × Fin (n μ))`, rewriting the parent's
-- `Fin (finrank V)` into `Fin (card)`; the single sub-goal `block_enum_of_card` (stated over
-- `Fin (card)`, with no T / b / Mμ / V) then supplies the contiguous-in-order enumeration.
-- Strictly simpler: it sheds 6 hypotheses and the FiniteDimensional layer, leaving `n : K → ℕ`.
/-- Given a finite-dimensional `K`-vector space `V` with a basis indexed by `(μ : K) × Fin (n μ)`
in which `T` is represented as a block-diagonal matrix of Jordan blocks, there exists an
enumeration `Fin (finrank K V) ≃ (μ : K) × Fin (n μ)` such that consecutive flat indices within
the same Jordan block correspond exactly to consecutive fiber indices. -/
theorem jordan_block_enumeration
    [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ)) :
    ∃ e : Fin (Module.finrank K V) ≃ ((μ : K) × Fin (n μ)),
      ∀ p q : Fin (Module.finrank K V), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ))) := by
  -- `finrank_eq_card_basis b` rewrites `Fin (finrank V)` to `Fin (card)`; then the
  -- index-combinatorics core `block_enum_of_card` (no T/matrices) supplies the enumeration.
  have hcard : Module.finrank K V = Fintype.card ((μ : K) × Fin (n μ)) :=
    Module.finrank_eq_card_basis b
  rw [hcard]
  exact block_enum_of_card

end

end Library.LinearAlgebra.JordanForm.BlockEnum
