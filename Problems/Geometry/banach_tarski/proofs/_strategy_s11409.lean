import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Factor the scalar `(1/3)` out of the word product by induction on the list.
-- Each generator equals `(1/3) •` its un-normalized integer matrix (hypotheses
-- `hA … hBInv`), so the head term `f x = (1/3) • g x` (via `← smul_ite` collecting
-- the branches), and the cons step combines `(r • _) * (s • _) = (r*s) • (_ * _)`
-- through `smul_mul_assoc`, `mul_smul_comm`, `smul_smul`, matching `pow_succ'`.
-- Direct leaf proof — no sub-goals.
theorem s11409
    (A AInv B BInv MA MAInv MB MBInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3 : ℝ) • MA) (hAInv : AInv = (1/3 : ℝ) • MAInv)
    (hB : B = (1/3 : ℝ) • MB) (hBInv : BInv = (1/3 : ℝ) • MBInv)
    (l : List (Fin 2 × Bool)) :
    (l.map (fun x : Fin 2 × Bool =>
        if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv))).prod
    = (1/3 : ℝ) ^ l.length •
      (l.map (fun x : Fin 2 × Bool =>
        if x.1 = 0 then (if x.2 then MA else MAInv) else (if x.2 then MB else MBInv))).prod := by
  subst hA hAInv hB hBInv
  induction l with
  | nil => simp
  | cons x xs ih =>
    rw [List.map_cons, List.prod_cons, List.map_cons, List.prod_cons, ih,
      List.length_cons, pow_succ', ← smul_ite, ← smul_ite, ← smul_ite,
      smul_mul_assoc, mul_smul_comm, smul_smul]

end Problems.Geometry.banach_tarski
