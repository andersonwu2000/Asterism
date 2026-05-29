import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- ρ''T = T∖D via direct set-extensionality (no decomposition needed; leaf-bypass).
-- LHS = ⋃ₙ ρⁿ⁺¹''D = the union missing its n=0 term. After `ext`/`simp [mem_iUnion,mem_diff]`:
--   ⊇ (backward): x∈ρⁿ''D∧x∉D ⇒ n≠0 (else x∈ρ⁰''D=D, contra hxD) ⇒ x∈ρ^(m+1)''D.
--   ⊆ (forward):  x∈ρⁿ⁺¹''D ⇒ trivially in the full union; x∉D since x∈ρ⁰''D=D would
--                 collide with x∈ρⁿ⁺¹''D under hdisj (0≠n+1).
theorem s11484 (D : Set E) (ρ : E ≃ᵢ E)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    (⋃ n : ℕ, (ρ ^ (n+1)) '' D) = (⋃ n : ℕ, (ρ ^ n) '' D) \ D  := by
  have hD0 : (ρ ^ (0:ℕ)) '' D = D := by simp
  ext x
  simp only [Set.mem_iUnion, Set.mem_diff]
  constructor
  · rintro ⟨n, hn⟩
    refine ⟨⟨n+1, hn⟩, ?_⟩
    intro hxD
    have h0 : x ∈ (ρ ^ (0:ℕ)) '' D := by rw [hD0]; exact hxD
    exact (hdisj (by omega : (0:ℕ) ≠ n+1)).le_bot ⟨h0, hn⟩
  · rintro ⟨⟨n, hn⟩, hxD⟩
    cases n with
    | zero => rw [hD0] at hn; exact absurd hn hxD
    | succ m => exact ⟨m, hn⟩

end Problems.Geometry.banach_tarski
