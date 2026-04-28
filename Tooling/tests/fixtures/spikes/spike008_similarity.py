"""spike-008 — IH-trap similarity metric comparison.

Implements Token Jaccard and Identifier Overlap metrics, tests against
a synthetic case set of IH-trap and non-IH-trap Lean goal statements.

Run: python Tooling/tests/fixtures/spikes/spike008_similarity.py

Output: per-case metric values + FP/FN rates for each metric.
"""

import re
import sys
import textwrap

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------------------
# Metric implementations
# ---------------------------------------------------------------------------

_LEAN_KEYWORDS = frozenset({
    "theorem", "lemma", "def", "example", "by", "intro", "induction", "cases",
    "apply", "exact", "simp", "rfl", "ring", "omega", "decide", "norm_num",
    "have", "show", "from", "fun", "let", "in", "match", "with", "where",
    "import", "open", "namespace", "end", "section", "variable", "noncomputable",
    "instance", "class", "structure", "extends", "deriving", "mutual",
    "forall", "exists", "And", "Or", "Not", "True", "False", "Prop", "Type",
    "Nat", "Int", "List", "Set", "Finset", "Real", "Bool",
    "if", "then", "else", "do", "return", "pure",
})

_LEAN_OPERATORS = frozenset({
    "∀", "∃", "→", "↔", "∧", "∨", "¬", "=", "≠", "≤", "≥", "<", ">",
    "+", "-", "*", "/", "^", "%", "::", "++", "∩", "∪", "⊆", "⊇",
    ":=", ":", ".", ",", "(", ")", "[", "]", "{", "}", "|", "⊢",
    "?", "!", "@", "#", "∘", "⟨", "⟩", "⟪", "⟫",
})


def _tokenize(s: str) -> list[str]:
    """Split on whitespace + punctuation boundary; keep non-empty tokens."""
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_'\.]*|[^\s\w]", s)
    return [t for t in tokens if t.strip()]


def token_jaccard(s1: str, s2: str) -> float:
    """Jaccard similarity on token sets (bag-of-words, de-duplicated)."""
    t1 = set(_tokenize(s1))
    t2 = set(_tokenize(s2))
    if not t1 and not t2:
        return 1.0
    return len(t1 & t2) / len(t1 | t2)


def _extract_identifiers(s: str) -> set[str]:
    """Extract Lean identifiers: alphanumeric tokens minus keywords/operators."""
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_'\.]*", s)
    return {t for t in tokens if t not in _LEAN_KEYWORDS}


def identifier_overlap(s1: str, s2: str) -> float:
    """Jaccard on extracted Lean identifier sets (keywords/ops excluded)."""
    i1 = _extract_identifiers(s1)
    i2 = _extract_identifiers(s2)
    if not i1 and not i2:
        return 1.0
    if not i1 or not i2:
        return 0.0
    return len(i1 & i2) / len(i1 | i2)


# ---------------------------------------------------------------------------
# Synthetic case set
# ---------------------------------------------------------------------------
# Each case: (label, parent_stmt, subgoal_stmt, is_ih_trap)
#   is_ih_trap=True  → the sub-goal IS an IH-trap (desired: flagged as similar)
#   is_ih_trap=False → NOT an IH-trap (desired: NOT flagged)
#
# IH-trap definition: subgoal is structurally near-identical to parent,
# differing only in the induction argument (e.g. P → P.erase x, l → l.tail).
# If the sub-goal is essentially the same as the parent the IH cannot help.

CASES = [
    # ── IH-trap cases (positive class) ─────────────────────────────────────
    (
        "IH-trap-1: list erase shrinks set (Sylvester-Gallai style)",
        "∀ (P : Finset ℕ), 3 ≤ P.card → (∀ p ∈ P, ∃ q ∈ P, p ≠ q) → ∃ x ∈ P, True",
        "∀ (P : Finset ℕ), 3 ≤ (P.erase x).card → (∀ p ∈ P.erase x, ∃ q ∈ P.erase x, p ≠ q) → ∃ x ∈ P.erase x, True",
        True,
    ),
    (
        "IH-trap-2: list tail shrinks list (length induction)",
        "∀ (l : List ℕ), l.length > 0 → ∃ x, x ∈ l",
        "∀ (l : List ℕ), l.tail.length > 0 → ∃ x, x ∈ l.tail",
        True,
    ),
    (
        "IH-trap-3: nat pred (arithmetic induction)",
        "∀ (n : ℕ), n > 0 → ∃ k, n = k + 1",
        "∀ (n : ℕ), n - 1 > 0 → ∃ k, n - 1 = k + 1",
        True,
    ),
    (
        "IH-trap-4: tree subtree (structural recursion)",
        "∀ (t : Tree ℕ), t.size > 0 → t.depth ≤ t.size",
        "∀ (t : Tree ℕ), t.left.size > 0 → t.left.depth ≤ t.left.size",
        True,
    ),
    (
        "IH-trap-5: set subset (monotone binder shift)",
        "∀ (S : Finset ℕ), S.card ≥ 2 → ∃ x y ∈ S, x ≠ y ∧ x + y > 0",
        "∀ (S : Finset ℕ), (S \\ {a}).card ≥ 2 → ∃ x y ∈ S \\ {a}, x ≠ y ∧ x + y > 0",
        True,
    ),
    # ── Non-IH-trap cases (negative class: surface similar but semantically distinct)
    (
        "non-IH-1: commutativity subgoal (semantically different conclusion)",
        "∀ (a b : ℕ), a + b = b + a",
        "∀ (a b : ℕ), a * b = b * a",
        False,
    ),
    (
        "non-IH-2: induction base case (structurally different)",
        "∀ (n : ℕ), n + 0 = n",
        "0 + 0 = 0",
        False,
    ),
    (
        "non-IH-3: list nil vs cons split",
        "∀ (l : List ℕ), l ++ [] = l",
        "[] ++ [] = []",
        False,
    ),
    (
        "non-IH-4: different predicate, same binder",
        "∀ (n : ℕ), n > 0 → n ≥ 1",
        "∀ (n : ℕ), n > 0 → n ≠ 0",
        False,
    ),
    (
        "non-IH-5: helper lemma (unrelated statement)",
        "∀ (P : Finset ℕ), 3 ≤ P.card → ∃ p ∈ P, True",
        "∀ (a b : ℕ), a ≤ b → a + 1 ≤ b + 1",
        False,
    ),
    # ── Boundary cases ──────────────────────────────────────────────────────
    (
        "boundary-1: alpha-rename only (∀ x → ∀ y)",
        "∀ (x : ℕ), x + 0 = x",
        "∀ (y : ℕ), y + 0 = y",
        False,  # NOT an IH-trap; α-equiv, same proof applies
    ),
    (
        "boundary-2: single quantifier drop (genuine IH-trap boundary)",
        "∀ (n m : ℕ), n ≤ m → n + 1 ≤ m + 1",
        "∀ (n : ℕ), n ≤ n → n + 1 ≤ n + 1",
        True,  # degenerate sub-goal that mirrors structure
    ),
]


# ---------------------------------------------------------------------------
# Threshold for flagging as IH-trap (from phase3_cache.md default)
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLD = 0.85


def run() -> None:
    print("=" * 72)
    print("spike-008  IH-trap similarity metric comparison")
    print("=" * 72)
    print(f"Threshold: {DEFAULT_THRESHOLD}")
    print()

    header = f"{'Case':<50}  {'TJ':>6}  {'IO':>6}  {'GT':>8}"
    print(header)
    print("-" * 72)

    results = []
    for label, parent, subgoal, is_ih_trap in CASES:
        tj = token_jaccard(parent, subgoal)
        io = identifier_overlap(parent, subgoal)
        results.append((label, tj, io, is_ih_trap))
        gt_label = "TRAP" if is_ih_trap else "ok"
        short = label[:48]
        print(f"{short:<50}  {tj:>6.3f}  {io:>6.3f}  {gt_label:>8}")

    print()

    # ── Evaluate each metric ─────────────────────────────────────────────
    for metric_name, idx in [("Token Jaccard", 1), ("Identifier Overlap", 2)]:
        tp = fp = tn = fn = 0
        for label, tj, io, is_ih_trap in results:
            score = (tj if idx == 1 else io)
            predicted = score >= DEFAULT_THRESHOLD
            if is_ih_trap and predicted:
                tp += 1
            elif not is_ih_trap and predicted:
                fp += 1
            elif is_ih_trap and not predicted:
                fn += 1
            else:
                tn += 1

        total_pos = tp + fn
        total_neg = fp + tn
        fpr = fp / total_neg if total_neg else 0.0
        fnr = fn / total_pos if total_pos else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0

        print(f"── {metric_name} @ threshold={DEFAULT_THRESHOLD} ──")
        print(f"   TP={tp}  FP={fp}  TN={tn}  FN={fn}")
        print(f"   False Positive Rate : {fpr:.3f}  ({fp}/{total_neg} non-traps flagged)")
        print(f"   False Negative Rate : {fnr:.3f}  ({fn}/{total_pos} traps missed)")
        print(f"   Precision           : {prec:.3f}")
        print(f"   Recall              : {rec:.3f}")
        print()

    # ── Threshold sweep ──────────────────────────────────────────────────
    print("── Threshold sweep (Token Jaccard) ──")
    print(f"  {'Thresh':>6}  {'FPR':>6}  {'FNR':>6}  {'Prec':>6}  {'Rec':>6}")
    for thresh in [0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        tp = fp = tn = fn = 0
        for _, tj, _, is_ih_trap in results:
            predicted = tj >= thresh
            if is_ih_trap and predicted:
                tp += 1
            elif not is_ih_trap and predicted:
                fp += 1
            elif is_ih_trap and not predicted:
                fn += 1
            else:
                tn += 1
        total_pos = tp + fn
        total_neg = fp + tn
        fpr = fp / total_neg if total_neg else 0.0
        fnr = fn / total_pos if total_pos else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        print(f"  {thresh:>6.2f}  {fpr:>6.3f}  {fnr:>6.3f}  {prec:>6.3f}  {rec:>6.3f}")

    print()
    print("── Threshold sweep (Identifier Overlap) ──")
    print(f"  {'Thresh':>6}  {'FPR':>6}  {'FNR':>6}  {'Prec':>6}  {'Rec':>6}")
    for thresh in [0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        tp = fp = tn = fn = 0
        for _, _, io, is_ih_trap in results:
            predicted = io >= thresh
            if is_ih_trap and predicted:
                tp += 1
            elif not is_ih_trap and predicted:
                fp += 1
            elif is_ih_trap and not predicted:
                fn += 1
            else:
                tn += 1
        total_pos = tp + fn
        total_neg = fp + tn
        fpr = fp / total_neg if total_neg else 0.0
        fnr = fn / total_pos if total_pos else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        print(f"  {thresh:>6.2f}  {fpr:>6.3f}  {fnr:>6.3f}  {prec:>6.3f}  {rec:>6.3f}")


if __name__ == "__main__":
    run()
