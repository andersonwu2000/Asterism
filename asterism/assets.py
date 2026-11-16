"""The pages' own files under /static: their bytes, and an address that names their content.

A page asks for /static/<name>?v=<version>, the version being a digest of what the file holds now; such an address is
served to be kept for good (it never holds anything else), so moving from page to page takes the stylesheet, the
scripts and above all the fonts from the browser's cache instead of loading them again: a font that arrives after the
first paint is drawn first in the fallback font and then swapped (the flash on changing pages, f6). A stylesheet's
own references (url(...) of a font) are given their versions when it is served, so the stylesheet's version also
changes when a font it names changes. An address without the version, or with an old one, is served to be checked
again each time (ETag), as before.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent / "static"
# url(...) in a stylesheet: a relative address of a file (not data:, not absolute, no query or fragment yet).
_CSS_URL_RE = re.compile(r"""url\((["']?)(?![a-z]+:|/|#)([^)"'?#]+)\1\)""")

_cache: dict[Path, tuple[float, int, bytes, str]] = {}      # path -> (mtime, size, bytes as served, version)


def _read(path: Path) -> tuple[bytes, str]:
    st = path.stat()
    kept = _cache.get(path)
    if kept and kept[0] == st.st_mtime and kept[1] == st.st_size:
        return kept[2], kept[3]
    raw = path.read_bytes()
    if path.suffix == ".css":
        raw = _versioned_css(path, raw)
    version = hashlib.sha256(raw).hexdigest()[:16]
    _cache[path] = (st.st_mtime, st.st_size, raw, version)
    return raw, version


def _versioned_css(path: Path, raw: bytes) -> bytes:
    text = raw.decode("utf-8")

    def one(m: re.Match[str]) -> str:
        target = (path.parent / m.group(2)).resolve()
        if not target.is_relative_to(STATIC) or not target.is_file():
            return m.group(0)
        return f"url({m.group(1)}{m.group(2)}?v={_read(target)[1]}{m.group(1)})"
    return _CSS_URL_RE.sub(one, text).encode("utf-8")


def resolve(name: str) -> Path | None:
    """The file under /static that `name` names, or None."""
    path = (STATIC / name).resolve()
    return path if path.is_relative_to(STATIC) and path.is_file() else None


def content(path: Path) -> tuple[bytes, str]:
    """(the bytes to serve, their version)."""
    return _read(path)


def url(name: str) -> str:
    """The address of a page's file that names its content: /static/<name>?v=<version>."""
    path = resolve(name)
    return f"/static/{name}" + (f"?v={_read(path)[1]}" if path else "")
