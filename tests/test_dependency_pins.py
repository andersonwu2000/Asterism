"""Every declared dependency needs a ceiling, not just a floor.

pyproject.toml carried floors alone until 2026-07-30. CI resolves fresh on
every run, so `mcp>=1.27` meant "whatever PyPI holds this hour": mcp 2.0.0
shipped 2026-07-28 without `mcp.server.fastmcp`, both blocking jobs died in
collection, and the gate stayed red for two days on code nobody had touched.
The same gap had already made CI green against starlette 1.3.1 while the
daemon ran 0.52.1 — a major apart, silently.

The rule is uniform so there is nothing to adjudicate per package: floor at
the verified version, ceiling at the next major (a 0.x package's next major
is 1). Crossing a ceiling is then a decision — bump, migrate, re-verify —
instead of an outage. .github/workflows/deps-drift.yml is what keeps that
from becoming ignorance of upstream.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _declared() -> list[tuple[str, str]]:
    """(section, requirement string) for every runtime and extra dependency."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    out = [("dependencies", r) for r in project["dependencies"]]
    for extra, reqs in project.get("optional-dependencies", {}).items():
        out += [(f"optional-dependencies.{extra}", r) for r in reqs]
    return out


def test_every_dependency_is_bounded_on_both_sides():
    unbounded = []
    for section, raw in _declared():
        req = Requirement(raw)
        ops = {spec.operator for spec in req.specifier}
        has_floor = bool(ops & {">=", ">", "==", "~="})
        has_ceiling = bool(ops & {"<", "<=", "==", "~="})
        if not (has_floor and has_ceiling):
            missing = "ceiling" if has_floor else "floor" if has_ceiling else "both"
            unbounded.append(f"{section}: {raw} (missing {missing})")
    assert not unbounded, (
        "dependencies must be bounded on both sides — an upstream major "
        "release must not be able to break the gate on its own:\n  "
        + "\n  ".join(unbounded)
    )


def test_ceilings_sit_at_the_next_major():
    """A ceiling below the next major turns routine upstream minors into red.

    The 2026-07-28 outage was a major; ceilings tighter than that would trade
    it for a steady drip of unrelated failures.
    """
    offenders = []
    for section, raw in _declared():
        req = Requirement(raw)
        for spec in req.specifier:
            if spec.operator != "<":
                continue
            parts = spec.version.split(".")
            # "<2" / "<10" — a bare major is the shape we want.
            if len(parts) == 1 and parts[0].isdigit():
                continue
            offenders.append(f"{section}: {raw} (ceiling {spec.version} is not a bare major)")
    assert not offenders, (
        "pin ceilings at the next major only:\n  " + "\n  ".join(offenders)
    )


def test_pytest_addopts_only_names_flags_the_extras_can_supply():
    """A config knob and the dependency that makes it legal move together.

    2026-08-11 `addopts = "-n auto"` landed without `pytest-xdist` in the
    dev extra. pytest does not warn about an unknown flag — it exits 4
    on a usage error BEFORE collecting anything, so both CI jobs went
    red without running a single test, and stayed red for a day while
    the local suite (which had xdist from elsewhere) was green. The
    declaration and the environment disagreed and only the remote one
    was honest.
    """
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    addopts = data["tool"]["pytest"]["ini_options"].get("addopts", "")
    dev = {Requirement(r).name
           for r in data["project"]["optional-dependencies"]["dev"]}
    #: flag in addopts -> the distribution that defines it
    needs = {"-n": "pytest-xdist", "--cov": "pytest-cov",
             "--forked": "pytest-forked", "--timeout": "pytest-timeout"}
    for flag, dist in needs.items():
        if flag in addopts.split():
            assert dist in dev, (
                f"addopts passes {flag} but the dev extra does not install "
                f"{dist} — pytest exits 4 on an unrecognised argument, "
                f"before it collects anything")
