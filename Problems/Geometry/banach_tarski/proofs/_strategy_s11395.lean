import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct list induction: matrix-product action realizes the foldr.
-- nil: empty product = 1, foldr base = v; simp closes mulVec 1 (embed v) = embed v.
-- cons: prod_cons + mulVec_mulVec peel genMat x off, ih handles the tail,
--   hstep rewrites mulVec (genMat x) (embed _) into embed (step x _) = foldr cons.
theorem s11395
    {R : Type*} [Semiring R] {n : Type*} [Fintype n] [DecidableEq n]
    {α σ : Type*}
    (embed : σ → (n → R)) (genMat : α → Matrix n n R) (step : α → σ → σ)
    (hstep : ∀ (x : α) (v : σ), Matrix.mulVec (genMat x) (embed v) = embed (step x v))
    (L : List α) (v : σ) :
    Matrix.mulVec ((L.map genMat).prod) (embed v) = embed (L.foldr step v)  := by
  induction L with
  | nil => simp
  | cons x xs ih =>
    rw [List.map_cons, List.prod_cons, List.foldr_cons,
        ← Matrix.mulVec_mulVec, ih, hstep]

end Problems.Geometry.banach_tarski
