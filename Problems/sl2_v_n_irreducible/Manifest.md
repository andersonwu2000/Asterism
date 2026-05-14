---
problem: sl2_v_n_irreducible
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# sl2_v_n_irreducible — every cyclic highest-weight sl₂-module is irreducible

## Statement
∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0),
  ∀ (W : LieSubmodule R L M),
    W ≤ LieSubmodule.lieSpan R L {v} →
    W = ⊥ ∨ W = LieSubmodule.lieSpan R L {v}

## Entry kind
Backward

## Strategic notes

Classical content (Humphreys §7): every cyclic highest-weight sl₂-module
of integer highest weight `n` is irreducible, and its underlying vector
space is the (n+1)-dim span of `{v, f·v, f²·v, …, fⁿ·v}` — this is the
standard `V_n` familiar from any first course on Lie theory.

Mathlib provides the underlying `IsSl2Triple` / `HasPrimitiveVectorWith`
machinery (file `Mathlib.Algebra.Lie.Sl2`, Oliver Nash 2024) — including
the keystone facts that the weight must be a non-negative integer and
that powers of `f` annihilate `v` past the n-th. The classification
itself (V_n is the unique irreducible (n+1)-dim representation), and
the irreducibility of the cyclic module produced by these primitives,
do not appear to be stated in Mathlib as named theorems.

Standard proof of irreducibility (Humphreys 7.2):
- Let `W ≤ lieSpan R L {v}` be a non-zero sub-LieSubmodule.
- Any element of `W` is a linear combination `∑ aₖ · fᵏ · v`, since
  `lieSpan R L {v}` is spanned by these vectors (h and e acting on
  `fᵏ·v` give scalar multiples / multiples of `fᵏ⁻¹·v`, both already
  in the span).
- Pick `w ∈ W \ {0}`; let `m` be the largest index with `aₘ ≠ 0`.
- Apply `eᵐ` to `w`. By the sl₂ commutation rules, only the `aₘ fᵐ v`
  term survives, scaled by a non-zero rational coefficient.
- Hence `v ∈ W`. By cyclicity, `W = lieSpan R L {v}`.

## Lemma hints

- `IsSl2Triple.HasPrimitiveVectorWith.exists_nat` — weight is `n : ℕ`
- `IsSl2Triple.HasPrimitiveVectorWith.pow_toEnd_f_ne_zero_of_eq_nat` —
  `fᵏ·v ≠ 0` for `0 ≤ k ≤ n`
- `IsSl2Triple.HasPrimitiveVectorWith.pow_toEnd_f_eq_zero_of_eq_nat` —
  `fᵏ·v = 0` for `k > n`
- `IsSl2Triple.HasPrimitiveVectorWith.lie_h_pow_toEnd_f` — h-weight of
  `fᵏ·v` is `n - 2k`
- `IsSl2Triple.HasPrimitiveVectorWith.lie_e_pow_succ_toEnd_f` — the
  e-action descent formula on `fᵏ·v`
- `LieSubmodule.lieSpan` / `LieSubmodule.mem_lieSpan`
- Distinct-eigenvalue → linear independence (standard linear algebra)

## Decomposition hint

Backward should decompose into roughly six sub-goals:
1. `{v, f·v, …, fⁿ·v}` are non-zero (for `0 ≤ k ≤ n`).
2. `fⁿ⁺¹·v = 0` and higher powers also vanish.
3. `{v, f·v, …, fⁿ·v}` are linearly independent (use distinct h-weights).
4. `lieSpan R L {v} = span_R {fᵏ·v | 0 ≤ k ≤ n}` (closure under sl₂).
5. Any non-zero element of `lieSpan R L {v}` can be reduced via repeated
   `e`-action to a non-zero scalar multiple of `v`.
6. Any non-zero sub-LieSubmodule contains `v`, hence equals the whole span.
