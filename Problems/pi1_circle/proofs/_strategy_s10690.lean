import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_winding_quotient_data

namespace Problems.pi1_circle

-- Strip the `End`/`FundamentalGroup` wrapping by performing the construction one
-- layer down on `Path.Homotopic.Quotient (1:Circle) 1` (the underlying Hom-set
-- of `FundamentalGroupoid Circle`). The sub-goal asks for W' on the quotient
-- with refl/trans/bijective; the combinator transports those properties through
-- `FundamentalGroup.toPath` (an abbrev; defeq up to `End.one_def`, `End.mul_def`,
-- and `FundamentalGroupoid.comp = Path.Homotopic.Quotient.trans`) and uses
-- `Quotient.ind` to expose path representatives for the multiplicative case.
theorem s10690 :
    ∃ (W : FundamentalGroup Circle 1 → ℤ),
      W 1 = 0 ∧
      (∀ a b : FundamentalGroup Circle 1, W (a * b) = W a + W b) ∧
      Function.Bijective W  := by
  have h_data := winding_quotient_data
  obtain ⟨W', h_one, h_trans, h_bij⟩ := h_data
  refine ⟨fun a => W' (FundamentalGroup.toPath a), ?_, ?_, ?_⟩
  · exact h_one
  · intro a b
    induction a using Quotient.ind with
    | _ γa =>
    induction b using Quotient.ind with
    | _ γb =>
    change W' (⟦γb.trans γa⟧ : Path.Homotopic.Quotient (1 : Circle) 1)
        = W' (⟦γa⟧ : Path.Homotopic.Quotient (1 : Circle) 1)
          + W' (⟦γb⟧ : Path.Homotopic.Quotient (1 : Circle) 1)
    rw [h_trans γb γa]; ring
  · exact h_bij

end Problems.pi1_circle
