import Mathlib

namespace Library.Geometry.BanachTarski.TrigCountability

-- entry_kind: Builder
-- cos_zero_set_countable: {θ | cos θ = 0} is countable as the image of ℤ under n ↦ (2n+1)π/2
theorem cos_zero_set_countable : {θ : ℝ | Real.cos θ = 0}.Countable := by
  have heq : {θ : ℝ | Real.cos θ = 0} = Set.range (fun k : ℤ => (2 * k + 1) * Real.pi / 2) := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_range]
    rw [Real.cos_eq_zero_iff]
    constructor
    · rintro ⟨k, hk⟩; exact ⟨k, hk.symm⟩
    · rintro ⟨k, hk⟩; exact ⟨k, hk.symm⟩
  rw [heq]
  exact Set.countable_range _

-- Direct proof (leaf-bypass): a cosine level set {t | cos t = c} is countable.
-- Case-split on ∃ t₀, cos t₀ = c. If none, the set is empty. Otherwise
-- `Real.cos_eq_cos_iff` shows every solution t equals 2kπ ± t₀ for some k : ℤ,
-- so the set sits inside the union of two ℤ-indexed ranges (countable), and
-- `Set.Countable.mono` transports countability back.
theorem cos_level_set_countable (c : ℝ) :
    {t : ℝ | Real.cos t = c}.Countable  := by
  by_cases h : ∃ t₀ : ℝ, Real.cos t₀ = c
  · obtain ⟨t₀, ht₀⟩ := h
    have hcount :
        ((Set.range (fun k : ℤ => 2 * (k : ℝ) * Real.pi + t₀)) ∪
          (Set.range (fun k : ℤ => 2 * (k : ℝ) * Real.pi - t₀))).Countable :=
      (Set.countable_range _).union (Set.countable_range _)
    apply hcount.mono
    intro t ht
    simp only [Set.mem_setOf_eq] at ht
    have hcc : Real.cos t₀ = Real.cos t := by rw [ht₀, ht]
    rw [Real.cos_eq_cos_iff] at hcc
    obtain ⟨k, hk | hk⟩ := hcc
    · exact Or.inl ⟨k, hk.symm⟩
    · exact Or.inr ⟨k, hk.symm⟩
  · simp only [not_exists] at h
    have he : {t : ℝ | Real.cos t = c} = ∅ := by
      ext t
      simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false]
      exact h t
    rw [he]
    exact Set.countable_empty

-- Amplitude-phase witness via the complex argument: take ψ = arg ⟨a,b⟩.
-- Then cos ψ = re/‖z‖ = a/√(a²+b²) and sin ψ = im/‖z‖ = b/√(a²+b²); since
-- a≠0∨b≠0 gives ‖z‖=√(a²+b²)≠0, multiplying back cancels. Direct, no sub-goals.
theorem amplitude_phase_exists (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    ∃ ψ : ℝ, a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ ∧
      b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ := by
  have hz0 : (⟨a, b⟩ : ℂ) ≠ 0 := by
    simp only [ne_eq, Complex.ext_iff, Complex.zero_re, Complex.zero_im, not_and]
    rcases h with ha | hb <;> intro <;> simp_all
  have hnorm : ‖(⟨a, b⟩ : ℂ)‖ = Real.sqrt (a ^ 2 + b ^ 2) := by
    rw [Complex.norm_def, Complex.normSq_mk]; ring_nf
  refine ⟨Complex.arg ⟨a, b⟩, ?_, ?_⟩
  · rw [Complex.cos_arg hz0, hnorm]
    have : (⟨a, b⟩ : ℂ).re = a := rfl
    rw [this, mul_div_cancel₀]
    rw [ne_eq, ← hnorm]
    simpa using hz0
  · rw [Complex.sin_arg, hnorm]
    have : (⟨a, b⟩ : ℂ).im = b := rfl
    rw [this, mul_div_cancel₀]
    rw [ne_eq, ← hnorm]
    simpa using hz0

-- combo_zero_set_eq_cos_shift: amplitude-phase identity; cos φ·a − sin φ·b = √(a²+b²)·cos(φ+ψ),
-- so the zero set equals {cos(φ+ψ)=0} after cancelling the nonzero amplitude.
-- entry_kind: Builder
theorem combo_zero_set_eq_cos_shift (a b ψ : ℝ) (h : a ≠ 0 ∨ b ≠ 0)
    (ha : a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ)
    (hb : b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}
      = {φ : ℝ | Real.cos (φ + ψ) = 0} := by
  have hsqrt : Real.sqrt (a ^ 2 + b ^ 2) ≠ 0 := by
    intro h0
    have hle : a ^ 2 + b ^ 2 ≤ 0 :=
      Real.sqrt_eq_zero'.mp
        (le_antisymm (by linarith [Real.sqrt_nonneg (a ^ 2 + b ^ 2)]) (Real.sqrt_nonneg _))
    have ha0 : a = 0 := by nlinarith [sq_nonneg a, sq_nonneg b]
    have hb0 : b = 0 := by nlinarith [sq_nonneg a, sq_nonneg b]
    exact h.elim (· ha0) (· hb0)
  have hkey : ∀ φ : ℝ, Real.cos φ * a - Real.sin φ * b =
      Real.sqrt (a ^ 2 + b ^ 2) * Real.cos (φ + ψ) := fun φ => by
    rw [Real.cos_add]
    linear_combination Real.cos φ * ha - Real.sin φ * hb
  ext φ
  simp only [Set.mem_setOf_eq, hkey φ]
  constructor
  · intro heq; exact (mul_eq_zero.mp heq).resolve_left hsqrt
  · intro heq; exact mul_eq_zero.mpr (Or.inr heq)

-- entry_kind: Builder
theorem cos_shift_set_eq_image (ψ : ℝ) :
    {φ : ℝ | Real.cos (φ + ψ) = 0}
      = (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} := by aesop

-- Amplitude-phase: rewrite the level set through cos(φ+ψ), then transport by shift.
-- h1: cos φ·a − sin φ·b = √(a²+b²)·cos(φ+ψ) and √(a²+b²)≠0 collapse the LHS zero set
--     to {cos(φ+ψ)=0} (uses ha, hb, h);
-- h2: the pure shift identity {cos(φ+ψ)=0} = (·−ψ)''{cosθ=0} (no a,b dependence);
-- transitivity closes the parent — each sub-goal is a single, smaller set equality.
theorem combo_zero_set_eq (a b ψ : ℝ) (h : a ≠ 0 ∨ b ≠ 0)
    (ha : a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ)
    (hb : b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0} =
      (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0}  := by
  have h1 : {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}
      = {φ : ℝ | Real.cos (φ + ψ) = 0} :=
    combo_zero_set_eq_cos_shift a b ψ h ha hb
  have h2 : {φ : ℝ | Real.cos (φ + ψ) = 0}
      = (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} :=
    cos_shift_set_eq_image ψ
  exact h1.trans h2

-- Amplitude-phase reduction: choose ψ with a = r·cosψ, b = r·sinψ (r = √(a²+b²) ≠ 0),
-- so cosφ·a − sinφ·b = r·cos(φ+ψ); its zero set is {cos(φ+ψ)=0} = (·−ψ)''{cosθ=0}.
--   amplitude_phase_exists  — the phase witness ψ (via Complex.arg of a+b·I);
--   combo_zero_set_eq       — the set equality given that phase data.
theorem combo_zero_eq_cos_zero_shift (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    ∃ ψ : ℝ, {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0} =
      (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0}  := by
  obtain ⟨ψ, ha, hb⟩ := amplitude_phase_exists a b h
  exact ⟨ψ, combo_zero_set_eq a b ψ h ha hb⟩

-- Amplitude-phase reduction: a·cosφ − b·sinφ = r·cos(φ+ψ) (r≠0), so its zero set is the
-- cos-zero set {(2n+1)π/2} translated by −ψ. Two sub-goals:
--   cos_zero_set_countable      — the cos-zero set is countable (range over ℤ);
--   combo_zero_eq_cos_zero_shift — the parent zero set equals that set shifted by −ψ.
-- Countable image of a countable set closes the parent.
theorem cos_sin_combo_zero_countable (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}.Countable  := by
  have hcos := cos_zero_set_countable
  obtain ⟨ψ, hψ⟩ := combo_zero_eq_cos_zero_shift a b h
  rw [hψ]
  exact hcos.image _

end Library.Geometry.BanachTarski.TrigCountability
