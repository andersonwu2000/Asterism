import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10920 {ι : Type*} [Fintype ι] (k : ι → ℕ) {m : ℕ} (σ : ι ≃ Fin m)
    (ν : Fin m → ℕ) (hν : ∀ i, ν i = k (σ.symm i))
    (e : Fin (∑ i, ν i) ≃ Σ i : Fin m, Fin (ν i)) (o : Fin m → ℕ)
    (he : ∀ p : Fin (∑ i, ν i), (p : ℕ) = o (e p).1 + ((e p).2 : ℕ)) :
    ∃ (e' : Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s)) (o' : ι → ℕ),
      ∀ p : Fin (∑ s, k s), (p : ℕ) = o' (e' p).1 + ((e' p).2 : ℕ)  := by
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

end Problems.LinearAlgebra.jordan_normal_form
