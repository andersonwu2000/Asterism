---
problem: LinearAlgebra.invariant_factor_decomposition
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.invariant_factor_decomposition — Cyclic / invariant-factor decomposition

## Statement
∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (r : ℕ) (f : Fin r → Polynomial K),
    (∀ i, (f i).Monic) ∧
    (∀ i, ¬ IsUnit (f i)) ∧
    (∀ i j, i ≤ j → f i ∣ f j) ∧
    Nonempty (Module.AEval' T ≃ₗ[Polynomial K]
      DirectSum (Fin r)
        (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))

## Setting
- `K` an arbitrary field; `V` finite-dim `K`-vector space; `T : V →ₗ[K] V` an endomorphism.
- View `V` as a `K[X]`-module via `T` (`X • v = T v`): this is `Module.AEval' T`.
- Conclusion (the **invariant-factor / cyclic decomposition theorem**, structural core of
  rational canonical form): there are monic non-unit polynomials
  `f₁ ∣ f₂ ∣ … ∣ f_r` (the **invariant factors**, written here as `f : Fin r → K[X]` with
  `i ≤ j → f i ∣ f j`) and a `K[X]`-linear isomorphism
  `Module.AEval' T ≃ₗ[K[X]] ⨁ᵢ K[X] / (f i)`.
- `f_r` (the largest invariant factor) is the minimal polynomial of `T`; their product is the
  characteristic polynomial. (Not required by the statement, but the canonical choice.)

## Route

The **primary** decomposition `V ≅ ⨁ K[X]/(pⱼ^{eⱼ})` is available two ways; the genuinely new
work is recombining the primary pieces into the **invariant-factor** (divisibility-chain)
form. This is the hard, missing-from-mathlib step — budget the bulk of effort here.

1. **Get to torsion + primary form.** View `V` via `Module.AEval' T`. It is a finitely
   generated torsion `K[X]`-module: `Module.Finite` (finite-dim) +
   `Module.AEval.isTorsion_of_finiteDimensional`. Then either:
   - cite mathlib `Module.equiv_directSum_of_isTorsion` directly on `AEval' T` — gives
     `AEval' T ≃ₗ[K[X]] ⨁ⱼ K[X]/(pⱼ^{eⱼ})` (primary/prime-power form), **or**
   - cite the **Library** primary decomposition
     `Library.LinearAlgebra.PrimaryDecomposition.Basic.main` (operator-level
     `DirectSum.IsInternal` of `ker (pⱼ(T)^{eⱼ})`) and transport to the `AEval'` module
     picture. Prefer the mathlib module-equiv route — it lands already in module-iso form.
2. **Recombine primary → invariant factors (the crux).** Group the prime powers `pⱼ^{eⱼ}` by
   "slot": sort each prime's exponents descending; the k-th invariant factor `f_k` is the
   product over primes of that prime's k-th-largest power (CRT: coprime prime powers in one
   slot multiply into one cyclic factor `K[X]/(f_k)`). Divisibility `f₁ ∣ f₂ ∣ … ∣ f_r`
   falls out because each prime contributes a non-increasing exponent sequence. Tools:
   `IsCoprime` + CRT (`Ideal.quotientInfRingEquivPiQuotient` /
   `ZMod`-style `Ideal.quotientMulEquivQuotientProd` for coprime ideals in `K[X]`),
   `DirectSum` regrouping (`DirectSum.lequiv*`, `DirectSum.coeLinearMap`).
3. **Assemble** the regrouped equiv + the divisibility/monic/non-unit side conditions into
   the existential.

## Lemma hints

Library (stage-3 chain — cite, do not reconstruct):
- `Library.LinearAlgebra.PrimaryDecomposition.Basic.main` — primary decomposition
  `DirectSum.IsInternal (fun i => ker (aeval T (pᵢ^{eᵢ})))` with `minpoly = ∏ pᵢ^{eᵢ}`.
- `Library.LinearAlgebra.PrimaryDecomposition.KernelAeval.is_internal_ker_aeval_of_pairwise_coprime`
  — the CRT kernel-decomposition engine (coprime factors ⇒ internal direct sum of kernels).
- `Library.LinearAlgebra.PrimaryDecomposition.PolynomialFactorization.exists_finpow_factorization`
  — monic poly = ∏ distinct monic irreducibles ^ multiplicity.

Mathlib (foundational):
- `Module.AEval'`, `Module.AEval'.of`, `Module.AEval.isTorsion_of_finiteDimensional`.
- `Module.equiv_directSum_of_isTorsion`, `Module.equiv_free_prod_directSum`
  (PID structure theorem — primary form).
- `IsCoprime`, CRT for quotients (`Ideal.quotientInfRingEquivPiQuotient`,
  `Ideal.quotientMulEquivQuotientProd`), `Polynomial` UFD machinery.
- `DirectSum`, `DirectSum.lequiv`, `Submodule.span`, quotient-module instances.

## R1 — search before reconstructing (hard rule)

Before introducing any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the name/shape. Any hit → `Read`.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match/near-match exists: reuse + thin bridge. Do not rebuild the PID structure
   theorem, CRT, UFD factorization, or the `AEval'` K[X]-module machinery — mathlib has them;
   primary decomposition is in the Library.
4. Only after confirmed missing, inject a new Forward whose `## Forward rationale` first line
   states `Grep + Loogle confirmed missing` with searched keywords.

## Forbidden angles

- Stopping at the **primary** form `⨁ K[X]/(pⱼ^{eⱼ})` — that is mathlib's
  `equiv_directSum_of_isTorsion`, not the invariant-factor (divisibility-chain) form this
  problem asks for. The recombination is the point.
- Citing the entire result as a single mathlib theorem if you find one — surface via
  `RequestUserAmend`.
