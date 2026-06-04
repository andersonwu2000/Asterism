import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Direct assembly of the per-column sorting data into the global grid; no
-- sub-goals, the sorting is already supplied as hypotheses so only plumbing
-- remains.  Witness: r' := r, c i t := cvec t i, idx i := (pos (key i) ⟨i,rfl⟩, key i).
--   • monotonicity ← hmono;  key-match ← rfl;  value-match ← hval.
--   • no-empty-row ← hcover places an element in each row, hval+hw make it > 0.
--   • injectivity: the dependent `{j // key j = t}`-subtype transport is sidestepped
--     by factoring `idx` through the sigma column `Σ t, {j // key j = t}` — the map
--     `(pos p.1 p.2, p.1)` is injective (snd pins the column, then subst + hinj), and
--     `idx = · ∘ (i ↦ ⟨key i, ⟨i,rfl⟩⟩)` with the latter trivially injective.
--   • zero-padding: same column-transport handled by `subst hjv` before invoking hpad.

theorem s11587 {J : Type*} [Fintype J] (w : J → ℕ) (hw : ∀ j, 0 < w j)
    (s r : ℕ) (key : J → Fin s)
    (cvec : Fin s → Fin r → ℕ)
    (pos : ∀ t : Fin s, {j : J // key j = t} → Fin r)
    (hmono : ∀ t, Monotone (cvec t))
    (hinj : ∀ t, Function.Injective (pos t))
    (hval : ∀ t (j : {j : J // key j = t}), cvec t (pos t j) = w j.val)
    (hpad : ∀ t (k : Fin r), (∀ j, pos t j ≠ k) → cvec t k = 0)
    (hcover : ∀ k : Fin r, ∃ (t : Fin s) (j : {j : J // key j = t}), pos t j = k) :
    ∃ (r' : ℕ) (c : Fin r' → Fin s → ℕ) (idx : J → Fin r' × Fin s),
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      Function.Injective idx ∧
      (∀ i, (idx i).2 = key i) ∧
      (∀ i, c (idx i).1 (idx i).2 = w i) ∧
      (∀ k, ∃ t, 0 < c k t) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0)  := by
  refine ⟨r, fun i t => cvec t i, fun i => (pos (key i) ⟨i, rfl⟩, key i),
    ?_, ?_, ?_, ?_, ?_, ?_⟩
  · intro i j hij t
    exact hmono t hij
  · -- injectivity, via the injective placement on sigma columns
    have hF : Function.Injective
        (fun p : Σ t : Fin s, {j : J // key j = t} => (pos p.1 p.2, p.1)) := by
      rintro ⟨t, j⟩ ⟨t', j'⟩ h
      simp only [Prod.mk.injEq] at h
      obtain ⟨hp, ht⟩ := h
      subst ht
      rw [hinj t hp]
    intro a b hab
    have : (⟨key a, ⟨a, rfl⟩⟩ : Σ t : Fin s, {j : J // key j = t})
        = ⟨key b, ⟨b, rfl⟩⟩ := hF hab
    exact congrArg (fun p : Σ t : Fin s, {j : J // key j = t} => p.2.1) this
  · intro i
    rfl
  · intro i
    exact hval (key i) ⟨i, rfl⟩
  · intro k
    obtain ⟨t, j, hj⟩ := hcover k
    refine ⟨t, ?_⟩
    change 0 < cvec t k
    rw [← hj, hval t j]
    exact hw j.val
  · intro k t hk
    apply hpad t k
    intro j
    obtain ⟨jv, hjv⟩ := j
    subst hjv
    intro hcon
    exact hk jv (by change (pos (key jv) ⟨jv, rfl⟩, key jv) = (k, key jv); rw [hcon])

end Problems.LinearAlgebra.invariant_factor_decomposition
