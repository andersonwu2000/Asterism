"""Slice 1w step w2 (the program): a chosen computer writes repository files with its own git, from a partial bare
clone of its own, never touching a working copy; a stale base or a moved branch is a conflict. A local bare
repository stands in for GitHub (ASTERISM_GIT_REMOTE).

    python -m pytest tests/test_m1w2p.py -q
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from test_m1b import SLUG, build_world, until
from test_m1j2 import ENV2, exe, home, join  # noqa: F401  (fixtures)

GIT = shutil.which("git")
IDENT = {"GIT_AUTHOR_NAME": "Alice Tester", "GIT_AUTHOR_EMAIL": "alice@example.test",
         "GIT_COMMITTER_NAME": "Alice Tester", "GIT_COMMITTER_EMAIL": "alice@example.test"}


def git(*args, cwd=None) -> str:
    r = subprocess.run([GIT, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       env=dict(subprocess.os.environ, **IDENT))
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout.strip()


def blob_of(remote, path) -> str:
    return git("--git-dir", str(remote), "rev-parse", f"main:{path}")


def file_at(remote, path) -> str:
    return git("--git-dir", str(remote), "show", f"main:{path}")


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    if GIT is None:
        pytest.skip("git is not installed")
    root = tmp_path_factory.mktemp("w2p")
    remote = root / "lab.git"
    git("init", "--bare", "--initial-branch=main", str(remote))
    seed = root / "seed"
    git("clone", str(remote), str(seed))
    (seed / "notes").mkdir()
    (seed / "notes" / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (seed / "README.md").write_text("# Lab\n", encoding="utf-8")
    git("add", ".", cwd=seed)
    git("commit", "-m", "seed", cwd=seed)
    git("push", "origin", "HEAD:main", cwd=seed)
    world = build_world(root / "data", ENV2)
    world.remote, world.seed = remote, seed
    yield world
    world.srv.stop()


def test_a_chosen_computer_commits_and_pushes_with_its_own_git(exe, v, home):
    join(exe, home, v, "--client", "none", ASTERISM_GIT_REMOTE=str(v.remote), **IDENT)
    creds = v.alice.c.get(f"/{SLUG}/api/my").json()["credentials"]
    newest = max((c for c in creds if c["kind"] == "computer"), key=lambda c: c["id"])
    assert v.alice.c.post(f"/{SLUG}/api/me/writer", json={"credential": newest["id"]}).status_code == 200
    assert until(lambda: v.alice.c.get(f"/{SLUG}/api/files/can-write").json().get("can_write") is True, 30), \
        v.alice.c.get(f"/{SLUG}/api/files/can-write").json()

    base = blob_of(v.remote, "notes/plan.md")
    r = v.alice.c.post(f"/{SLUG}/api/files/save", json={"path": "notes/plan.md", "content": "# Plan\n\nstep two\n",
                                                          "base": base, "message": "Plan: step two"}, timeout=90)
    assert r.status_code == 200, r.text
    assert file_at(v.remote, "notes/plan.md") == "# Plan\n\nstep two"
    log = git("--git-dir", str(v.remote), "log", "-1", "--format=%an|%s", "main")
    assert log == "Alice Tester|Plan: step two", "the computer's own git identity and the message"
    assert r.json()["commit"] == git("--git-dir", str(v.remote), "rev-parse", "main")

    stale = blob_of(v.remote, "notes/plan.md")
    git("fetch", "origin", cwd=v.seed)
    git("reset", "--hard", "origin/main", cwd=v.seed)
    (v.seed / "notes" / "plan.md").write_text("pushed by someone else\n", encoding="utf-8")
    git("commit", "-am", "someone else", cwd=v.seed)
    git("push", "origin", "HEAD:main", cwd=v.seed)
    r = v.alice.c.post(f"/{SLUG}/api/files/save", json={"path": "notes/plan.md", "content": "mine\n", "base": stale},
                       timeout=90)
    assert r.status_code == 409 and r.json()["error"] == "conflict", r.text
    assert r.json()["current"] == blob_of(v.remote, "notes/plan.md")
    assert file_at(v.remote, "notes/plan.md") == "pushed by someone else", "nothing was written"

    r = v.alice.c.post(f"/{SLUG}/api/files/rename", json={"path": "README.md", "to": "docs/README.md",
                                                           "base": blob_of(v.remote, "README.md")}, timeout=90)
    assert r.status_code == 200, r.text
    names = git("--git-dir", str(v.remote), "ls-tree", "-r", "--name-only", "main").splitlines()
    assert "docs/README.md" in names and "README.md" not in names
    assert len(git("--git-dir", str(v.remote), "log", "--format=%H", "-1", "main", "--", "docs/README.md").splitlines()) == 1

    r = v.alice.c.post(f"/{SLUG}/api/files/delete", json={"path": "docs/README.md",
                                                           "base": blob_of(v.remote, "docs/README.md")}, timeout=90)
    assert r.status_code == 200, r.text
    assert "docs/README.md" not in git("--git-dir", str(v.remote), "ls-tree", "-r", "--name-only", "main")

    clones = list((home / "repos").glob("*.git"))
    assert len(clones) == 1 and (clones[0] / "HEAD").exists(), "a bare clone of its own, under the program's folder"
    assert git("--git-dir", str(clones[0]), "config", "--get", "remote.origin.partialclonefilter") == "blob:none"
