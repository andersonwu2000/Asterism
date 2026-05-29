import Problems.Geometry.banach_tarski.proofs.L_freegroup_starts_disjoint
namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem starts_disjoint {α : Type*} [DecidableEq α] :
    ∀ p q : α × Bool, p ≠ q →
        Disjoint {w : FreeGroup α | (FreeGroup.toWord w).head? = some p}
                 {w : FreeGroup α | (FreeGroup.toWord w).head? = some q} := by apply freegroup_starts_disjoint <;> assumption

end Problems.Geometry.banach_tarski
