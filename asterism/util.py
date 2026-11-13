"""Small shared pieces: secrets and their digests, names, times, the event log."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
GITHUB_LOGIN_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
# Top-level paths of the server; a project slug may not shadow them.
RESERVED_SLUGS = {"api", "login", "logout", "oauth", "test", "join", "static", "helper", "well-known", "mcp",
                  "device", "admin", "projects"}


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def digest(secret: str) -> str:
    """Secrets are only ever stored as this digest. Total: a lone surrogate (JSON allows "\\ud800") digests
    instead of raising, and matches nothing."""
    return hashlib.sha256(secret.encode("utf-8", "surrogatepass")).hexdigest()


def valid_name(name: Any) -> bool:
    return isinstance(name, str) and NAME_RE.fullmatch(name) is not None


def valid_slug(slug: Any) -> bool:
    return isinstance(slug, str) and SLUG_RE.fullmatch(slug) is not None and slug not in RESERVED_SLUGS


def now() -> float:
    return time.time()


def iso(t: float | None) -> str | None:
    if not t:
        return None
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_next(raw: Any) -> str:
    """Where to go after signing in: only ever a path on this server."""
    if not isinstance(raw, str) or not raw.startswith("/") or raw.startswith("//") or "\\" in raw:
        return "/"
    if any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in raw):
        return "/"
    parts = urllib.parse.urlsplit(raw)
    if parts.scheme or parts.netloc:
        return "/"
    return raw


def clean_label(raw: Any, limit: int = 80) -> str:
    """A free-text label shown on pages (computer name, client name): printable, bounded."""
    text = "".join(ch for ch in str(raw or "") if ch.isprintable()).strip()
    return text[:limit]


_log_lock = threading.Lock()
_log_path: Path | None = None


def set_log(path: Path) -> None:
    global _log_path
    _log_path = path


def log(event: str, **fields: Any) -> None:
    """One JSON line per event. Callers pass names and ids only, never a secret."""
    if _log_path is None:
        return
    line = json.dumps({"t": iso(now()), "event": event, **fields}, ensure_ascii=False)
    with _log_lock, open(_log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
