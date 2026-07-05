---
problem: Geometry.integration_current_stokes
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Geometry.integration_current_stokes — currents bridge keystone `∂[[e]] = [[∂e]]` (functional level)

## Statement
∀ {n : ℕ} {N : Type*} [compact oriented manifold-with-boundary on EuclideanHalfSpace (n+1)]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
  (e : N → F) (ψ : F → (F [⋀^Fin n]→L[ℝ] ℝ))
  (he : ContMDiff … ∞ e) (hψ : ContDiff ℝ ∞ ψ) (hdψ : ContDiff ℝ ∞ (extDeriv ψ)),
  integrationCurrent e (extDeriv ψ) he hdψ = boundaryIntegrationCurrent e ψ he hψ

## Strategic notes
**Capstone of the de Rham integration-current bridge.** This is classical Stokes expressed
as the currents boundary identity `∂[[e]] = [[∂e]]`, evaluated on a flat test `n`-form `ψ`:
`∂[[e]](ψ) = [[e]](dψ) = ∫_N e*(dψ) = ∫_N d(e*ψ) = ∫_{∂N} (e*ψ)|_{∂N} = [[∂e]](ψ)`.

Unfolding `integrationCurrent`/`boundaryIntegrationCurrent` (Defs.lean), the goal is
`DiffForm.integral (pullbackFlatForm e (extDeriv ψ) …) = DiffForm.integral (pullbackBdry (pullbackFlatForm e ψ …))`.
**Two-step leaf-bypass, both citations in Library:**

1. **d-step** — rewrite the LHS form via brick ②
   `Library.Geometry.ManifoldBdry.PullbackFlatDNat.mextDeriv_pullbackFlatForm`
   (`mextDeriv (𝓡∂ (n+1)) (pullbackFlatForm e ψ he hψ) = pullbackFlatForm e (extDeriv ψ) he hdψ`),
   used right-to-left so `pullbackFlatForm e (extDeriv ψ) …` becomes
   `mextDeriv (𝓡∂ (n+1)) (pullbackFlatForm e ψ he hψ)`.
2. **Stokes** — close with the Library keystone
   `Library.Geometry.Manifold.PerBumpStokes.integral_mextDeriv_eq_integral_pullbackBdry`
   (`∀ φ, DiffForm.integral (mextDeriv (𝓡∂ (n+1)) φ) = DiffForm.integral (pullbackBdry φ)`)
   applied to `φ := pullbackFlatForm e ψ he hψ`.

So: `simp only [integrationCurrent, boundaryIntegrationCurrent];
rw [← mextDeriv_pullbackFlatForm e ψ he hψ hdψ];
exact integral_mextDeriv_eq_integral_pullbackBdry (pullbackFlatForm e ψ he hψ)` (modulo
exact-name/implicit fiddling). No new analysis — the d-naturality (brick ②) and Stokes
(P13) are both done and harvested.

The only deferred piece of the bridge is the **continuity** that would make `ψ ↦ [[e]](ψ)`
a genuine topological-dual `Current` (a sup-norm bound on `DiffForm.integral`); not needed
for this functional-level identity.
