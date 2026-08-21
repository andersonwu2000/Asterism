"""Ratchet on the settings page's key allowlist.

`UI_EDITABLE_KEYS` is what the Engine → Settings page renders as
controls, and a control is a promise that turning it does something.
After the v33 worker merge the page kept offering `builder.model`,
`backward.model` and `forward.model` for months — pipelines that no
longer run, each one describing ITSELF in its own tooltip as "unread
post-v33" (owner, 2026-08-07). Nothing caught it because nothing was
watching the set.

Same shape as `test_transitions_lint.py`: a pinned set, so adding or
retiring a control is a deliberate edit here with a reason, not a
silent drift.
"""
from __future__ import annotations

from Tooling.core.config import MODEL_CHOICES, UI_EDITABLE_KEYS

#: every control the settings page is allowed to render. Changing this
#: set means changing what the page promises — say why in the commit.
_PINNED = {
    # models — one per pipeline the engine actually spawns today, and
    # the backend that runs each: three are live (claude / antigravity /
    # codex) and `<kind>.provider` was yaml-only until 2026-08-14
    "formalizer.provider",
    "strategist.provider",
    "presearch.provider",
    "librarian.provider",
    "adversary.provider",
    "formalizer.model",
    "strategist.model",
    "presearch.model",
    "librarian.model",
    "adversary.model",
    # dispatch knobs a mathematician tunes
    "dispatch.pool",
    "dispatch.budget_sec",
    "dispatch.shelve_threshold",
    "dispatch.quota_wait",
}


def test_key_set_is_pinned() -> None:
    assert set(UI_EDITABLE_KEYS) == _PINNED


def test_no_control_describes_itself_as_dead() -> None:
    """A page that renders a knob while calling it legacy/unread is
    telling the user two contradictory things; the knob loses."""
    for key, (_typ, desc) in UI_EDITABLE_KEYS.items():
        low = desc.lower()
        for word in ("legacy", "unread", "deprecated", "no longer"):
            assert word not in low, (
                f"{key} is offered as a control but describes itself as"
                f" {word!r}: {desc!r}. Retire the control or fix the words."
            )


def test_model_choices_are_not_empty_and_have_no_blank() -> None:
    """The UI renders `choices` verbatim as options. A blank one would
    be indistinguishable from the unset placeholder the page adds when
    a key has no value."""
    assert MODEL_CHOICES
    assert all(c.strip() for c in MODEL_CHOICES)


def test_every_seat_can_choose_both_its_model_and_its_backend() -> None:
    """The two key families are generated from one seat list, so a seat
    can never end up with a model picker and no way to say which
    backend runs it."""
    from Tooling.core.config import UI_EDITABLE_KEYS, UI_SEATS
    for seat in UI_SEATS:
        assert f"{seat}.model" in UI_EDITABLE_KEYS, seat
        assert f"{seat}.provider" in UI_EDITABLE_KEYS, seat


def test_a_model_picker_never_offers_another_backends_names() -> None:
    """The select exists to kill "a typo'd model only explodes at the
    NEXT run". A flat claude-only list did exactly that one level up,
    offering `claude-fable-5` for a codex seat."""
    from Tooling.core.config import MODEL_CHOICES_BY_PROVIDER, models_for
    for prov, names in MODEL_CHOICES_BY_PROVIDER.items():
        assert names, prov
        for other, theirs in MODEL_CHOICES_BY_PROVIDER.items():
            if other != prov:
                assert not (set(names) & set(theirs)), (prov, other)
    # an undeclared backend yields NO list — the UI must then take free
    # text, never another backend's names
    assert models_for("no-such-backend") == []
