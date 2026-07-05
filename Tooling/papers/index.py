"""Navigation index (paper map): one-shot LLM spawn, no pipeline (D9).

`generate_index` renders the prompt template, spawns a single agent
whose cwd is the paper's shelf dir, and expects it to write `map.md`.
The framework then stamps frontmatter binding the map to the exact
`text_sha` it was built from — staleness is mechanical, never trusted
to the agent (mirrors the DB↔file pairing discipline).

Small-doc exemption: papers under `shelf.INDEX_MIN_CHARS` get no map;
the Context section points agents at text.md directly.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from . import shelf

# Context injection budget shares the pool with presearch candidates
# (teammate note 2026-07-06); the prompt asks for < 6000, the hard
# presentation cap in context.py is PAPER_INDEX_MAX_CHARS.
MAP_TARGET_CHARS = 6_000


def generate_index(workspace: Path, pid: str, *, prompt_dir: Path,
                   force: bool = False) -> Path | None:
    """Build/rebuild `Papers/<pid>/map.md`. Returns the map path, or
    None when exempt (small doc) — loud errors otherwise."""
    meta = shelf.load_meta(workspace, pid)
    if meta is None:
        raise FileNotFoundError(
            f"no shelved paper {pid!r} (run paper-add first)")
    if meta.chars < shelf.INDEX_MIN_CHARS and not force:
        print(f"[papers] {pid}: {meta.chars} chars < "
              f"{shelf.INDEX_MIN_CHARS} — small-doc exemption, no index "
              f"(agents read text.md whole; --force to override)",
              flush=True)
        return None

    template = prompt_dir / "papers" / "paper_index.md"
    pdir = shelf.paper_dir(workspace, pid)
    tpath = shelf.text_path(workspace, pid)
    mpath = shelf.map_path(workspace, pid)
    sandbox = pdir / ".index_attempt"
    sandbox.mkdir(parents=True, exist_ok=True)
    rendered = (
        template.read_text(encoding="utf-8")
        .replace("__TEXT_PATH__", tpath.as_posix())
        .replace("__MAP_PATH__", mpath.as_posix())
        .replace("__TARGET_CHARS__", str(MAP_TARGET_CHARS))
    )
    prompt_file = sandbox / "prompt.md"
    prompt_file.write_text(rendered, encoding="utf-8")
    try:
        mpath.unlink()
    except OSError:
        pass

    from ..core import config
    from .. import agent
    timeout = int(config.get("paper_index.timeout_sec", default=1200))
    agent.spawn_llm(
        kind="paper_index", prompt_path=prompt_file,
        problem_dir=pdir, attempts_dir=sandbox,
        session_id=str(uuid.uuid4()),
        timeout_sec_override=timeout,
    )

    if not mpath.is_file():
        raise RuntimeError(
            f"paper_index agent finished without writing {mpath}")
    body = mpath.read_text(encoding="utf-8")
    # Framework-stamped staleness binding; strip any agent-written
    # frontmatter so the stamp is the only authority.
    if body.startswith("---"):
        end = body.find("---", 3)
        if end != -1:
            body = body[end + 3:].lstrip("\n")
    stamped = (f"---\npaper: {pid}\ntext_sha: {meta.text_sha}\n---\n\n"
               + body)
    mpath.write_text(stamped, encoding="utf-8")
    if len(stamped) > 2 * MAP_TARGET_CHARS:
        print(f"[papers] WARN {pid}: map.md is {len(stamped)} chars "
              f"(target {MAP_TARGET_CHARS}) — will be truncated at "
              f"Context injection; consider regenerating", flush=True)
    print(f"[papers] indexed {pid} → {mpath} ({len(stamped)} chars)",
          flush=True)
    return mpath
