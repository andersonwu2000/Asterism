"""Oracle ARM64 readiness P0#4 — zen shim attempt-path recognition on
POSIX.

`zen_shim._ATTEMPT_RE` is the FALLBACK channel: `_attempt_dir_of`
regex-scans the whole request body for a `.attempts/<uuid>` substring
when the deterministic URL channel (`/a/<relpath>/v1`, platform-neutral
already) missed. Until this fix the regex only recognized Windows
drive paths, so on a Linux box the fallback silently returned
`attempt_dir=None` for every request it had to cover — tool writes
refused, or context attributed to the wrong spawn.

Extending the regex to also match POSIX absolute paths widens what it
accepts, so `_attempt_dir_of` must now fence the match: resolve it and
reject anything that doesn't land inside THIS workspace's `.attempts`
tree (a `..` escape, or a syntactically valid path naming some OTHER
repo's `.attempts`). See `_fence_attempt_candidate`'s docstring for why
the check is done with `posixpath.normpath` on a slash-normalized
string rather than `pathlib.Path.resolve()` — the point that makes
these tests possible on a Windows CI host in the first place.
"""
from __future__ import annotations

import pytest

from Tooling.llm import zen_shim

UUID = "c505e391-1cde-4be4-b3c2-407f89796ef7"


def _body(text: str) -> dict:
    return {"instructions": text, "input": []}


def test_windows_drive_path_still_recognized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", r"C:\Asterism")
    hay = _body(rf"cwd is C:\Asterism\.attempts\{UUID} for this turn")
    assert zen_shim._attempt_dir_of(hay) == f"C:/Asterism/.attempts/{UUID}"


def test_posix_absolute_path_now_recognized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", "/home/ubuntu/Asterism")
    hay = _body(f"cwd is /home/ubuntu/Asterism/.attempts/{UUID} for this turn")
    assert (zen_shim._attempt_dir_of(hay)
            == f"/home/ubuntu/Asterism/.attempts/{UUID}")


def test_mixed_slashes_in_a_windows_path_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", r"C:\Asterism")
    hay = _body(f"cwd is C:/Asterism/.attempts/{UUID} for this turn")
    assert zen_shim._attempt_dir_of(hay) == f"C:/Asterism/.attempts/{UUID}"


def test_surrounding_whitespace_in_the_haystack_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", "/home/ubuntu/Asterism")
    hay = _body(
        f"\n\n  some preamble text   "
        f"  /home/ubuntu/Asterism/.attempts/{UUID}  \n"
        f"  more trailing text\n")
    assert (zen_shim._attempt_dir_of(hay)
            == f"/home/ubuntu/Asterism/.attempts/{UUID}")


def test_nested_projection_dir_is_carried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", "/home/ubuntu/Asterism")
    hay = _body(
        f"cwd is /home/ubuntu/Asterism/.attempts/{UUID}/adversary/r2")
    assert (zen_shim._attempt_dir_of(hay)
            == f"/home/ubuntu/Asterism/.attempts/{UUID}/adversary/r2")


def test_dotdot_escape_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", "/home/ubuntu/Asterism")
    hay = _body(
        f"cwd is /home/ubuntu/Asterism/.attempts/{UUID}"
        f"/../../../etc/passwd")
    assert zen_shim._attempt_dir_of(hay) is None


def test_foreign_tree_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Syntactically a perfectly valid `.attempts/<uuid>` path — just
    not inside THIS workspace. The regex alone cannot tell; the fence
    must."""
    monkeypatch.setattr(zen_shim, "_REPO", "/home/ubuntu/Asterism")
    hay = _body(f"cwd is /home/ubuntu/SomeOtherRepo/.attempts/{UUID}")
    assert zen_shim._attempt_dir_of(hay) is None


def test_windows_escape_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", r"C:\Asterism")
    hay = _body(rf"cwd is C:\Asterism\.attempts\{UUID}\..\..\Windows\System32")
    assert zen_shim._attempt_dir_of(hay) is None


def test_no_match_still_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim, "_REPO", "/home/ubuntu/Asterism")
    assert zen_shim._attempt_dir_of(_body("nothing path-shaped here")) is None


def test_fence_helper_rejects_root_itself_without_trailing_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity check on the fence in isolation: the workspace root
    exactly is accepted (edge of the `==` branch), a sibling directory
    that merely shares the prefix textually is not."""
    monkeypatch.setattr(zen_shim, "_REPO", "/home/ubuntu/Asterism")
    root = zen_shim._attempts_root_norm()
    assert zen_shim._fence_attempt_candidate(root) == root
    assert zen_shim._fence_attempt_candidate(root + "-evil-sibling") is None
