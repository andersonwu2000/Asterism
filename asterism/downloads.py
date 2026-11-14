"""Downloads: the builds of the resident program under DIR/dist/, described by DIR/dist/manifest.json
(written at deploy time), and the install scripts generated for this server's public address.

A file is served only when the manifest lists its name, and the path is built from the manifest's entry,
never from the request: nothing in the URL can reach another file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

KEY_RE = re.compile(r"(windows|macos|linux)-(x64|arm64)")
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
SCRIPTS = Path(__file__).resolve().parent / "install"
PLACEHOLDER = "@ASTERISM_URL@"


def manifest(data: Path) -> dict[str, Any]:
    """The manifest, with only the well-formed entries; {"version": None, "files": {}} when there is none."""
    try:
        raw = json.loads((data / "dist" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = None
    if not isinstance(raw, dict):
        return {"version": None, "files": {}}
    files = {}
    for key, f in (raw.get("files") if isinstance(raw.get("files"), dict) else {}).items():
        if KEY_RE.fullmatch(key) and isinstance(f, dict) and isinstance(f.get("name"), str) \
                and NAME_RE.fullmatch(f["name"]) and isinstance(f.get("sha256"), str) \
                and SHA256_RE.fullmatch(f["sha256"].lower()):
            files[key] = dict(f, sha256=f["sha256"].lower())
    version = raw.get("version")
    return {"version": version if isinstance(version, str) else None, "files": files}


def program(data: Path) -> dict[str, Any]:
    """{version, available}: whether the server has any build of the program to hand out."""
    m = manifest(data)
    return {"version": m["version"], "available": bool(m["files"])}


def public_manifest(data: Path, public_url: str) -> dict[str, Any]:
    m = manifest(data)
    return {"version": m["version"],
            "files": {k: dict(f, url=f"{public_url}/dl/{f['name']}") for k, f in m["files"].items()}}


def build(data: Path, name: str) -> Path | None:
    """The file of a build the manifest lists under this name, or None."""
    for f in manifest(data)["files"].values():
        if f["name"] == name:
            path = data / "dist" / f["name"]
            return path if path.is_file() else None
    return None


def install_script(which: str, public_url: str) -> str:
    """install.sh (POSIX sh, LF line ends) or install.ps1 (Windows PowerShell 5.1), for this server."""
    text = (SCRIPTS / which).read_text(encoding="utf-8").replace("\r\n", "\n")
    if which == "install.sh":
        quoted = "'" + public_url.replace("'", "'\\''") + "'"
    else:
        quoted = "'" + public_url.replace("'", "''") + "'"
        text = text.replace("\n", "\r\n")
    return text.replace(PLACEHOLDER, quoted)
