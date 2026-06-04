import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_block_assembly
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_block_companion

namespace Problems.LinearAlgebra.rational_canonical_form

-- Split assembly (basis transport) from per-block companion identification.
-- `block_assembly` builds the K-basis (DFinsupp of per-block power bases, transported
--   through `e` and `Module.AEval'.of T`) and shows `toMatrix b b T` is the block diagonal
--   of the per-block "multiply by root" operator matrices — pure functorial transport, no
--   polynomial arithmetic.
-- `block_companion` identifies each per-block operator matrix with `companionMatrix (f i)`
--   (the %ₘ-coefficient computation), so the two pieces are strictly simpler than the parent.
-- Combine: rewrite by `block_assembly`, then `congr`/`funext` and discharge each block by
--   `block_companion`.
theorem s11592 {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (hmonic : ∀ i, (f i).Monic)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :
    ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
      LinearMap.toMatrix b b T
        = Matrix.blockDiagonal' (fun i => companionMatrix (f i))  := by
  obtain ⟨b, hb⟩ := block_assembly T f hmonic e
  refine ⟨b, ?_⟩
  rw [hb]
  congr 1
  funext i
  exact block_companion (hmonic i)

end Problems.LinearAlgebra.rational_canonical_form
