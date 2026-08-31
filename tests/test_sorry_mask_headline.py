"""#5 sorry-mask headline (owner approval 2026-08-31).

Field: a backward parent citing five deliberate-`sorry` outsourced stubs
validated as `ok: true, 0 diagnostics, no sorries` — the stubs' sorry
warnings are (correctly) dropped as noise, and the CONDITIONAL verdict
lived only in the buried `parity` block. 21 reports; 4 on 08-31 alone
(p357/corrected_overlay_level_crossing_transfer, p617/s27360_gamma_chain,
p617/weighted_symmetric_incidence_gamma_bound). Soundness held throughout
(wait-edges + promote gates); the HEADLINE lied by omission.

Contract: when the green is conditional — parity says an inlined sibling
is unproved, or a citation gate warns an imported goal is unproved
(shelved included) — the response carries `conditional_on` (the slugs)
and `conditional_note` DIRECTLY AFTER `ok`, so the qualifier cannot be
missed by a reader that stops at the headline.
"""
from __future__ import annotations

from Tooling.lsp.gateway.verify import _hoist_conditional


def _resp(parity, citation=None):
    r = {"ok": True, "file": "patch.lean", "diagnostic_count": 0,
         "diagnostics": [], "parity": parity,
         "submission": {"annotation": {"checked": True, "ok": True}}}
    if citation is not None:
        r["submission"]["citation"] = citation
    return r


def test_conditional_parity_hoists_to_headline():
    r = _hoist_conditional(_resp(
        {"state": "conditional", "depends_on": ["s2_beta", "s2_alpha"],
         "note": "..."}))
    assert r["conditional_on"] == ["s2_alpha", "s2_beta"]
    assert r["conditional_note"]
    keys = list(r)
    assert keys.index("conditional_on") == keys.index("ok") + 1, \
        "the qualifier must sit beside the headline, not below the fold"


def test_citation_warns_join_the_headline_errors_do_not():
    r = _hoist_conditional(_resp(
        {"state": "conditional", "depends_on": ["s1_a"]},
        citation={"ok": True, "issues": [
            {"slug": "shelved_dep", "status": "shelved", "severity": "warn",
             "hint": "resolved later"},
            {"slug": "dead_dep", "status": "dead", "severity": "error",
             "hint": "rejected at commit"}]}))
    assert r["conditional_on"] == ["s1_a", "shelved_dep"], \
        "warn = unproved dependency; error is a rejection, not a condition"


def test_exact_parity_stays_clean():
    r = _hoist_conditional(_resp(
        {"state": "exact", "proved_siblings": ["s1_a"]}))
    assert "conditional_on" not in r and "conditional_note" not in r


def test_unresolved_parity_is_not_softened_into_a_condition():
    # unresolved = framework defect with its own loud note; folding it
    # into "conditional" would relabel a defect as legitimate waiting.
    r = _hoist_conditional(_resp(
        {"state": "unresolved", "framework_parity_error": ["ghost"]}))
    assert "conditional_on" not in r
