"""The project's GitHub repository, read-only: the head of its default branch, its folders one at a time, and
its files as raw bytes. Nothing is ever written to GitHub.

Reaching GitHub: with an app configured (an id and a private key), the server signs a short-lived token as the
app, finds the app's installation on the repository and asks for an installation token that can only read
contents; the token is kept until shortly before it expires. Without an app, or when it is not installed there,
the server asks without credentials, which works for a public repository. Only GET requests go to GitHub, plus
the one POST that asks for the installation token; redirects are never followed.

Freshness: the head is trusted for ASTERISM_FILES_REFRESH_S; inside that time GitHub is not asked for what is
cached. Trees and blobs are addressed by their hash and never change: each is fetched once and kept on disk
under DATA/cache/<project>/ (trees as JSON, blobs as their bytes, served from the disk). The folder never holds
more than ASTERISM_FILES_CACHE_MB after an answer: what was used longest ago (file modification time, touched on
every use) goes first. Deleting the folder at any time is harmless.

Three states per project: connected; GitHub away (no answer, 5xx, rate limited: what is cached is served and
listings are marked stale); not connected (the repository is not readable: 409). Each is checked again after
the refresh time, so recovering or installing the app needs no restart.
"""
from __future__ import annotations

import asyncio
import base64
import codecs
import json
import os
import re
import secrets
import shutil
import threading
import time
import urllib.parse
import weakref
from calendar import timegm
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

import anyio
import httpx

from . import config, util
from .errors import ApiError, bad_request, not_found

HASH_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
OWNER_RE = util.GITHUB_LOGIN_RE
REPO_NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,100}")
RESOLVE_MOST = 200
CHUNK = 64 * 1024
TOKEN_MARGIN_S = 300            # an installation token is renewed this long before it expires
APP_TOKEN_LIFE_S = 540          # the app's own token: issued 60 s in the past, so 600 s in all (GitHub's limit)
TMP_PREFIX = "tmp-"
TMP_STALE_S = 3600              # a partial download older than this was left by a crash
API_VERSION = "2022-11-28"
TIMEOUT = httpx.Timeout(20, connect=5)

BAD_PATH = ("A path is folder and file names joined by '/', without empty, '.' or '..' names, backslashes or "
            "control characters.")
UNAVAILABLE = "GitHub is not answering right now, and this was not read before. Try again in a little while."
NO_READ = "Reading the project needs the read permission."

TEXT = "text/plain; charset=utf-8"
BINARY = "application/octet-stream"
TEXT_SUFFIXES = {
    ".md", ".markdown", ".tex", ".sty", ".cls", ".bst", ".bbl", ".lean", ".txt", ".text", ".bib", ".json", ".toml",
    ".yaml", ".yml", ".py", ".pyi", ".ipynb", ".html", ".htm", ".xhtml", ".xml", ".css", ".js", ".mjs", ".cjs", ".ts",
    ".tsx", ".jsx", ".c", ".h", ".cc", ".cpp", ".hpp", ".rs", ".go", ".java", ".kt", ".hs", ".ml", ".jl", ".r",
    ".m", ".sage", ".gp", ".g", ".sh", ".bash", ".ps1", ".bat", ".csv", ".tsv", ".ini", ".cfg", ".conf", ".rst",
    ".org", ".log", ".lock", ".diff", ".patch", ".sql", ".lua", ".rb", ".pl", ".php", ".v", ".agda", ".thy", ".coq",
}
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
         ".webp": "image/webp", ".svg": "image/svg+xml", ".pdf": "application/pdf"}
CSP_SANDBOX = "default-src 'none'; sandbox"
CSP_PDF = "default-src 'none'; frame-ancestors 'self'"


# --------------------------------------------------------------------------- the repository's address

@dataclass(frozen=True)
class Repo:
    owner: str
    name: str

    @property
    def full(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def web(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"


def parse_repo(address: Any) -> Repo | None:
    """`https://github.com/{owner}/{name}` (a trailing '/' or '.git' is allowed); anything else is None."""
    if not isinstance(address, str):
        return None
    parts = urllib.parse.urlsplit(address.strip())
    if parts.scheme != "https" or (parts.hostname or "").lower() != "github.com" or parts.port is not None \
            or parts.username or parts.password or parts.query or parts.fragment:
        return None
    segs = parts.path.strip("/").split("/")
    if len(segs) != 2:
        return None
    owner, name = segs
    if name.endswith(".git"):
        name = name[:-4]
    if not OWNER_RE.fullmatch(owner) or not REPO_NAME_RE.fullmatch(name) or name in (".", ".."):
        return None
    return Repo(owner, name)


def not_connected(repo: Repo | None, address: str) -> ApiError:
    if repo is None:
        shown = util.clean_label(address, 200)
        return ApiError(409, "not_connected",
                        f"The project's repository ({shown}) is not a GitHub repository address of the form "
                        "https://github.com/owner/name, so its files cannot be shown here.")
    return ApiError(409, "not_connected",
                    f"This server cannot read the GitHub repository {repo.full}. The project's owner installs the "
                    "server's GitHub app on that repository; the files then appear here by themselves.")


def unavailable() -> ApiError:
    return ApiError(502, "github_unavailable", UNAVAILABLE)


# --------------------------------------------------------------------------- paths

def _bad_char(text: str) -> bool:
    return "\\" in text or any(ord(ch) < 0x20 or 0x7f <= ord(ch) <= 0x9f for ch in text)


def split_path(raw: Any, folder: bool = False) -> list[str] | None:
    """The names of a path in the repository, or None when it is not one. A folder may be empty (the root) and
    may end with one '/'."""
    if not isinstance(raw, str) or _bad_char(raw) or len(raw) > 4096:
        return None
    if folder:
        if raw.endswith("/"):
            raw = raw[:-1]
        if raw == "":
            return []
    segs = raw.split("/")
    if any(s in ("", ".", "..") for s in segs):
        return None
    return segs


def check_path(raw: Any, folder: bool = False) -> list[str]:
    segs = split_path(raw, folder)
    if segs is None:
        raise bad_request("invalid_path", BAD_PATH)
    return segs


# --------------------------------------------------------------------------- types of served files

def content_type(path: str) -> str | None:
    """The type a file is served as, from its extension; None: look at the bytes (UTF-8 text or not)."""
    name = path.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    suffix = name[dot:].lower() if dot > 0 else ""
    if suffix in TYPES:
        return TYPES[suffix]
    if suffix in TEXT_SUFFIXES:
        return TEXT
    return None


def is_utf8(f) -> bool:
    """Whether an open file holds UTF-8 text; it is read through and put back at its start."""
    dec = codecs.getincrementaldecoder("utf-8")()
    try:
        while chunk := f.read(CHUNK):
            dec.decode(chunk)
        dec.decode(b"", final=True)
        return True
    except UnicodeDecodeError:
        return False
    finally:
        f.seek(0)


def etag_matches(header: str | None, tag: str) -> bool:
    if not header:
        return False
    for part in header.split(","):
        p = part.strip()
        if p == "*" or (p[2:] if p.startswith("W/") else p) == tag:
            return True
    return False


# --------------------------------------------------------------------------- per-project state

@dataclass
class Head:
    ref: str
    commit: str
    tree: str


@dataclass
class State:
    mode: str = "unknown"                       # ok | away | not_connected | unknown
    head: Head | None = None
    next_check: float = 0.0                     # monotonic
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    installation: int | None = None
    token: str | None = None
    token_expires: float = 0.0                  # wall clock
    app_problem: str | None = None              # the app problem last written down


_states: dict[tuple[str, Repo], State] = {}
_client: httpx.AsyncClient | None = None
_fetch_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
_evict_lock = threading.Lock()


def _state(slug: str, repo: Repo) -> State:
    key = (slug, repo)
    if key not in _states:
        _states[key] = State()
    return _states[key]


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False,
                                    headers={"User-Agent": "asterism", "X-GitHub-Api-Version": API_VERSION})
    return _client


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _fetch_lock(key: str) -> asyncio.Lock:
    lock = _fetch_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _fetch_locks[key] = lock
    return lock


class _Away(Exception):
    """GitHub did not answer usefully: no answer, 5xx, rate limited, or an answer that makes no sense."""


class _Refused(Exception):
    """GitHub refused (401, 403, 404, 3xx): the repository is not readable this way."""


def _reason(r: httpx.Response) -> str:
    return f"http_{r.status_code}"


def _check(r: httpx.Response, ok: int = 200) -> None:
    if r.status_code == ok:
        return
    limited = r.status_code == 429 or (r.status_code == 403 and r.headers.get("x-ratelimit-remaining") == "0")
    if r.status_code >= 500 or limited:
        raise _Away("rate_limited" if limited else _reason(r))
    raise _Refused(_reason(r))


def _json(r: httpx.Response) -> dict[str, Any]:
    try:
        data = r.json()
    except ValueError:
        raise _Away("bad_answer") from None
    if not isinstance(data, dict):
        raise _Away("bad_answer")
    return data


async def _get(url: str, headers: dict[str, str]) -> httpx.Response:
    try:
        return await client().get(url, headers=headers)
    except httpx.HTTPError as e:
        raise _Away(type(e).__name__.lower()) from None


# --------------------------------------------------------------------------- the app's tokens

class _AppUnusable(Exception):
    pass


def _app() -> tuple[str, Path] | None:
    """(id, key path) when an app is configured, else None. The key named in the settings, or else
    DATA/github_app.pem when that file exists."""
    s = config.get()
    key = Path(s.github_app_key) if s.github_app_key else s.data / "github_app.pem"
    if not s.github_app_id or (not s.github_app_key and not key.is_file()):
        return None
    return s.github_app_id, key


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def app_token(app_id: str, key_path: Path) -> str:
    """The app's own token: a JWT signed with RS256, good for at most ten minutes. The key is read from its file
    each time and never kept."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError:
        raise _AppUnusable("cryptography_missing") from None
    try:
        pem = key_path.read_bytes()
    except OSError:
        raise _AppUnusable("app_key_unreadable") from None
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError):
        raise _AppUnusable("app_key_invalid") from None
    if not isinstance(key, rsa.RSAPrivateKey):
        raise _AppUnusable("app_key_invalid")
    now = int(time.time())
    iss: Any = int(app_id) if app_id.isdigit() else app_id
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({"iat": now - 60, "exp": now + APP_TOKEN_LIFE_S, "iss": iss},
                             separators=(",", ":")).encode())
    signed = f"{head}.{claims}".encode("ascii")
    return f"{head}.{claims}." + _b64(key.sign(signed, padding.PKCS1v15(), hashes.SHA256()))


def _app_problem(slug: str, st: State, reason: str | None) -> None:
    if reason is not None and reason != st.app_problem:
        util.log("github_error", project=slug, reason=reason)
    st.app_problem = reason


def _expiry(raw: Any) -> float:
    try:
        return float(timegm(time.strptime(str(raw), "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return time.time() + 600


async def _auth(slug: str, repo: Repo, st: State) -> dict[str, str]:
    """The headers to read the repository with: the installation token when there is one, else nothing."""
    base = {"Accept": "application/vnd.github+json"}
    app = _app()
    if app is None:
        return base
    if st.token and st.token_expires - TOKEN_MARGIN_S > time.time():
        return dict(base, Authorization=f"Bearer {st.token}")
    st.token = None
    app_id, key_path = app
    try:
        jwt = app_token(app_id, key_path)
    except _AppUnusable as e:
        _app_problem(slug, st, str(e))
        return base
    as_app = dict(base, Authorization=f"Bearer {jwt}")
    api = config.get().github_api_url
    if st.installation is None:
        r = await _get(f"{api}/repos/{repo.owner}/{repo.name}/installation", as_app)
        if r.status_code == 404:                     # not installed there: ask without credentials
            _app_problem(slug, st, None)
            return base
        try:
            _check(r)
        except _Refused:
            _app_problem(slug, st, "app_refused_" + _reason(r))
            return base
        inst = _json(r).get("id")
        if not isinstance(inst, int) or isinstance(inst, bool) or inst <= 0:
            raise _Away("bad_answer")
        st.installation = inst
    try:
        r = await client().post(f"{api}/app/installations/{st.installation}/access_tokens", headers=as_app,
                                json={"repositories": [repo.name], "permissions": {"contents": "read"}})
    except httpx.HTTPError as e:
        raise _Away(type(e).__name__.lower()) from None
    try:
        _check(r, 201)
    except _Refused:
        st.installation = None                       # uninstalled or changed: looked up again next time
        _app_problem(slug, st, "app_refused_" + _reason(r))
        return base
    answer = _json(r)
    token = answer.get("token")
    if not isinstance(token, str) or not token or _bad_char(token) or " " in token:
        raise _Away("bad_answer")
    st.token, st.token_expires = token, _expiry(answer.get("expires_at"))
    _app_problem(slug, st, None)
    return dict(base, Authorization=f"Bearer {token}")


# --------------------------------------------------------------------------- the head

def _enter(slug: str, st: State, mode: str, reason: str | None = None) -> None:
    """Change state; a change into trouble is written down once."""
    if mode != st.mode and mode in ("away", "not_connected"):
        util.log("github_error", project=slug, reason=reason)
    st.mode = mode


async def _read_head(slug: str, repo: Repo, st: State) -> None:
    api = config.get().github_api_url
    base = f"{api}/repos/{repo.owner}/{repo.name}"
    headers = await _auth(slug, repo, st)
    r = await _get(base, headers)
    if r.status_code == 401 and st.token:            # the token went bad early: one more try with a new one
        st.token = None
        headers = await _auth(slug, repo, st)
        r = await _get(base, headers)
    _check(r)
    ref = _json(r).get("default_branch")
    if not isinstance(ref, str) or not ref or len(ref) > 255 or _bad_char(ref):
        raise _Away("bad_answer")
    r = await _get(f"{base}/branches/{urllib.parse.quote(ref, safe='')}", headers)
    _check(r)
    commit = _json(r).get("commit")
    sha = commit.get("sha") if isinstance(commit, dict) else None
    inner = commit.get("commit") if isinstance(commit, dict) else None
    tree = inner.get("tree") if isinstance(inner, dict) else None
    root = tree.get("sha") if isinstance(tree, dict) else None
    if not isinstance(sha, str) or not isinstance(root, str) or not HASH_RE.fullmatch(sha) \
            or not HASH_RE.fullmatch(root):
        raise _Away("bad_answer")
    if st.head is None or st.head.commit != sha:
        util.log("files_head", project=slug, commit=sha)
    st.head = Head(ref, sha, root)


async def _refresh(slug: str, repo: Repo, st: State) -> None:
    try:
        await _read_head(slug, repo, st)
        _enter(slug, st, "ok")
    except _Away as e:
        _enter(slug, st, "away", str(e))
    except _Refused as e:
        _enter(slug, st, "not_connected", str(e))
    st.next_check = time.monotonic() + config.get().files_refresh_s


async def head(slug: str, repo: Repo, force: bool = False) -> tuple[Head, bool]:
    """(the head, whether it may be old). Raises not_connected or github_unavailable."""
    st = _state(slug, repo)
    if force or time.monotonic() >= st.next_check:
        seen = st.next_check
        async with st.lock:
            if st.next_check == seen:                # nobody refreshed while we waited
                await _refresh(slug, repo, st)
    if st.mode == "not_connected":
        raise not_connected(repo, repo.web)
    if st.head is None:
        raise unavailable()
    return st.head, st.mode != "ok"


# --------------------------------------------------------------------------- the cache on disk

def cache_root() -> Path:
    return config.get().data / "cache"


def _cache_dir(slug: str) -> Path:
    return cache_root() / slug


def forget(slug: str) -> None:
    """A project was deleted: what is known and kept of its repository goes with it."""
    for key in [k for k in _states if k[0] == slug]:
        del _states[key]
    folder = _cache_dir(slug)
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def _touch(path: Path) -> None:
    try:
        os.utime(path)
    except OSError:
        pass


def _write_new(folder: Path, name: str) -> tuple[Path, Any]:
    """A new partial file in the cache folder, open for writing."""
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"{TMP_PREFIX}{secrets.token_hex(8)}-{name}"
    return tmp, open(tmp, "wb")


def _publish(tmp: Path, final: Path) -> None:
    """Move a finished download into place; what is there already has the same bytes."""
    try:
        os.replace(tmp, final)
    except OSError:
        if not final.exists():
            raise
        tmp.unlink(missing_ok=True)


def evict(root: Path, limit: int, keep: Path) -> None:
    """Remove what was used longest ago until the cache holds at most `limit` bytes. `keep` stays (just
    written, about to be served). A file that cannot be removed now (open elsewhere) is passed over."""
    with _evict_lock:
        files: list[tuple[float, int, Path]] = []
        total = 0
        now = time.time()
        try:
            folders = [p for p in root.iterdir() if p.is_dir()]
        except OSError:
            return
        for folder in folders:
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for e in entries:
                try:
                    st = e.stat()
                except OSError:
                    continue
                if not e.is_file():
                    continue
                if e.name.startswith(TMP_PREFIX):
                    if st.st_mtime < now - TMP_STALE_S:
                        Path(e.path).unlink(missing_ok=True)
                    continue
                total += st.st_size
                files.append((st.st_mtime, st.st_size, Path(e.path)))
        if total <= limit:
            return
        for _, size, path in sorted(files, key=lambda f: (f[0], str(f[2]))):
            if total <= limit:
                break
            if path == keep:
                continue
            try:
                path.unlink()
                total -= size
            except FileNotFoundError:
                total -= size
            except OSError:
                pass


def _limit() -> int:
    return int(config.get().files_cache_mb * 1024 * 1024)


# --------------------------------------------------------------------------- trees

@dataclass(frozen=True)
class Entry:
    name: str
    kind: str                                   # dir | file | other
    sha: str = ""
    size: int = 0


def _entries(tree: Any) -> list[Entry]:
    """GitHub's entries of one folder, made safe: a name that cannot be a path segment is dropped; anything that
    is not a plain folder or file, or has no usable hash, is `other` (shown, never fetched)."""
    if not isinstance(tree, list):
        raise _Away("bad_answer")
    out: list[Entry] = []
    for e in tree:
        if not isinstance(e, dict) or not isinstance(e.get("path"), str):
            continue
        name = e["path"]
        if name in ("", ".", "..") or "/" in name or "\x00" in name:
            continue
        sha, kind, mode, size = e.get("sha"), e.get("type"), e.get("mode"), e.get("size")
        usable = isinstance(sha, str) and HASH_RE.fullmatch(sha) is not None and not _bad_char(name)
        if usable and kind == "tree":
            out.append(Entry(name, "dir", sha))
        elif usable and kind == "blob" and mode in ("100644", "100755") and isinstance(size, int) \
                and not isinstance(size, bool) and size >= 0:
            out.append(Entry(name, "file", sha, size))
        else:
            out.append(Entry(name, "other"))
    return out


def _load_tree(path: Path) -> list[Entry] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return None                             # damaged: fetched again
    _touch(path)
    try:
        return [Entry(**e) for e in raw]
    except TypeError:
        return None


def _save_tree(folder: Path, sha: str, entries: list[Entry]) -> Path:
    tmp, f = _write_new(folder, sha)
    with f:
        f.write(json.dumps([e.__dict__ for e in entries], ensure_ascii=False).encode("utf-8"))
    final = folder / f"{sha}.tree"
    _publish(tmp, final)
    return final


class _Missing(Exception):
    """GitHub refused a tree or blob the head names: access changed since the head was read."""


async def _tree(slug: str, repo: Repo, sha: str) -> list[Entry]:
    if not HASH_RE.fullmatch(sha):              # never a file name otherwise
        raise _Away("bad_answer")
    folder = _cache_dir(slug)
    path = folder / f"{sha}.tree"
    got = await anyio.to_thread.run_sync(_load_tree, path)
    if got is not None:
        return got
    async with _fetch_lock(f"{slug}/{sha}.tree"):
        got = await anyio.to_thread.run_sync(_load_tree, path)
        if got is not None:
            return got
        st = _state(slug, repo)
        headers = await _auth(slug, repo, st)
        r = await _get(f"{config.get().github_api_url}/repos/{repo.owner}/{repo.name}/git/trees/{sha}", headers)
        try:
            _check(r)
        except _Refused:
            if r.status_code == 401:
                st.token = None
            raise _Missing(_reason(r)) from None
        entries = _entries(_json(r).get("tree"))
        written = await anyio.to_thread.run_sync(_save_tree, folder, sha, entries)
        await anyio.to_thread.run_sync(evict, cache_root(), _limit(), written)
        return entries


async def _walk(slug: str, repo: Repo, root: str, segs: list[str]) -> Entry | None:
    """The entry at this path (the root is a dir entry), or None."""
    here = Entry("", "dir", root)
    for name in segs:
        if here.kind != "dir":
            return None
        here = next((e for e in await _tree(slug, repo, here.sha) if e.name == name), None)
        if here is None:
            return None
    return here


# --------------------------------------------------------------------------- blobs

def _open(path: Path):
    try:
        f = open(path, "rb")
    except FileNotFoundError:
        return None
    _touch(path)
    return f


async def _download_blob(slug: str, repo: Repo, entry: Entry, final: Path) -> None:
    st = _state(slug, repo)
    headers = await _auth(slug, repo, st)
    headers["Accept"] = "application/vnd.github.raw+json"
    url = f"{config.get().github_api_url}/repos/{repo.owner}/{repo.name}/git/blobs/{entry.sha}"
    tmp, f = await anyio.to_thread.run_sync(_write_new, final.parent, entry.sha)
    done = False
    try:
        try:
            async with client().stream("GET", url, headers=headers) as r:
                try:
                    _check(r)
                except _Refused:
                    if r.status_code == 401:
                        st.token = None
                    raise _Missing(_reason(r)) from None
                count = 0
                async for chunk in r.aiter_bytes(CHUNK):
                    count += len(chunk)
                    if count > entry.size:
                        raise _Away("bad_answer")
                    await anyio.to_thread.run_sync(f.write, chunk)
                if count != entry.size:
                    raise _Away("bad_answer")
        except httpx.HTTPError as e:
            raise _Away(type(e).__name__.lower()) from None
        await anyio.to_thread.run_sync(f.close)
        await anyio.to_thread.run_sync(_publish, tmp, final)
        done = True
    finally:
        if not done:
            f.close()
            tmp.unlink(missing_ok=True)


async def _blob(slug: str, repo: Repo, entry: Entry):
    """An open file holding the blob's bytes, fetched first when it is not on disk."""
    if not HASH_RE.fullmatch(entry.sha):
        raise _Away("bad_answer")
    final = _cache_dir(slug) / f"{entry.sha}.blob"
    for _ in range(3):
        f = await anyio.to_thread.run_sync(_open, final)
        if f is not None:
            return f
        async with _fetch_lock(f"{slug}/{entry.sha}.blob"):
            if not await anyio.to_thread.run_sync(final.exists):
                await _download_blob(slug, repo, entry, final)
            f = await anyio.to_thread.run_sync(_open, final)
            if f is not None:
                await anyio.to_thread.run_sync(evict, cache_root(), _limit(), final)
                return f
    raise _Away("cache_unwritable")


# --------------------------------------------------------------------------- what the endpoints call

async def _guarded(slug: str, repo: Repo, work):
    """Run `work(head)`. GitHub away while fetching: github_unavailable (and the state says so). GitHub refusing
    what the head names: the head is read again at once, which tells whether the repository is still readable."""
    h, stale = await head(slug, repo)
    try:
        return await work(h), stale
    except _Away as e:
        _enter(slug, _state(slug, repo), "away", str(e))
        raise unavailable() from None
    except _Missing:
        await head(slug, repo, force=True)          # raises not_connected when it is so
        raise unavailable() from None


def _repo_of(address: str) -> Repo:
    repo = parse_repo(address)
    if repo is None:
        raise not_connected(None, address)
    return repo


async def listing(slug: str, address: str, raw_dir: Any) -> dict[str, Any]:
    segs = check_path(raw_dir if raw_dir is not None else "", folder=True)
    repo = _repo_of(address)
    folder = "/".join(segs)

    async def work(h: Head):
        e = await _walk(slug, repo, h.tree, segs)
        if e is None or e.kind != "dir":
            raise not_found(f"There is no folder '{folder}' in the repository.")
        return h, await _tree(slug, repo, e.sha)
    (h, entries), stale = await _guarded(slug, repo, work)
    rank = {"dir": 0, "file": 1, "other": 2}
    out = []
    for e in sorted(entries, key=lambda e: (rank[e.kind], e.name.casefold(), e.name)):
        item: dict[str, Any] = {"name": e.name, "path": f"{folder}/{e.name}" if folder else e.name, "type": e.kind}
        if e.kind == "file":
            item["size"] = e.size
        out.append(item)
    answer: dict[str, Any] = {"ref": h.ref, "commit": h.commit, "dir": folder, "entries": out}
    if stale:
        answer["stale"] = True
    return answer


@dataclass
class Served:
    """A file to send: an open handle, its size, its hash, and how to type it."""
    file: Any
    size: int
    sha: str
    ctype: str
    attachment: bool
    name: str


async def raw(slug: str, address: str, raw_path: Any, if_none_match: str | None) -> Served | str:
    """The file at this path, or its quoted ETag alone when `if_none_match` matches it (304)."""
    segs = check_path(raw_path)
    repo = _repo_of(address)
    path = "/".join(segs)
    max_bytes = int(config.get().files_max_mb * 1024 * 1024)

    async def work(h: Head):
        e = await _walk(slug, repo, h.tree, segs)
        if e is None or e.kind != "file":
            raise not_found(f"There is no file '{path}' in the repository.")
        tag = f'"{e.sha}"'
        if etag_matches(if_none_match, tag):
            return tag
        if e.size > max_bytes:
            where = repo.web + f"/blob/{urllib.parse.quote(h.ref, safe='')}/" + \
                "/".join(urllib.parse.quote(s, safe="") for s in segs)
            raise ApiError(413, "too_large",
                           f"This file is {e.size / 1024 / 1024:.1f} MB, more than the "
                           f"{config.get().files_max_mb:g} MB shown here. Open it on GitHub: {where}")
        f = await _blob(slug, repo, e)
        ctype = content_type(path)
        attachment = False
        if ctype is None:
            try:
                ctype = TEXT if await anyio.to_thread.run_sync(is_utf8, f) else BINARY
            except OSError:
                ctype = BINARY
            attachment = ctype == BINARY
        return Served(f, e.size, e.sha, ctype, attachment, segs[-1])
    out, _ = await _guarded(slug, repo, work)
    return out


async def resolve(slug: str, address: str, paths: Any) -> dict[str, Any]:
    if not isinstance(paths, list) or len(paths) > RESOLVE_MOST or not all(isinstance(p, str) for p in paths):
        raise bad_request("invalid_paths", f"paths must be a list of at most {RESOLVE_MOST} paths.")
    repo = _repo_of(address)

    async def work(h: Head):
        found: dict[str, str] = {}
        for p in dict.fromkeys(paths):
            segs = split_path(p)
            if segs is None:
                continue
            e = await _walk(slug, repo, h.tree, segs)
            if e is not None and e.kind in ("dir", "file"):
                found[p] = e.kind
        return {"found": found}
    out, _ = await _guarded(slug, repo, work)
    return out


# --------------------------------------------------------------------------- finding files by path

FIND_MOST = 200
FIND_DEFAULT = 50
FIND_Q_MOST = 200
# The last index read per project: (tree hash, index), so typing does not read the file on every key.
_indexes: dict[str, tuple[str, dict[str, Any]]] = {}


def _index_entries(tree: Any) -> list[list[str]]:
    """GitHub's recursive listing as [path, "file" | "dir"]; a path that is not a usable path, and anything that is
    neither a plain file nor a folder, is left out."""
    if not isinstance(tree, list):
        raise _Away("bad_answer")
    out: list[list[str]] = []
    for e in tree:
        if not isinstance(e, dict) or split_path(e.get("path")) is None:
            continue
        if e.get("type") == "tree":
            out.append([e["path"], "dir"])
        elif e.get("type") == "blob" and e.get("mode") in ("100644", "100755"):
            out.append([e["path"], "file"])
    return out


def _load_index(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None                             # missing or damaged: fetched again
    if not isinstance(raw, dict) or not isinstance(raw.get("paths"), list):
        return None
    _touch(path)
    return raw


def _save_index(folder: Path, sha: str, index: dict[str, Any]) -> Path:
    tmp, f = _write_new(folder, sha)
    with f:
        f.write(json.dumps(index, ensure_ascii=False).encode("utf-8"))
    final = folder / f"{sha}.index"
    _publish(tmp, final)
    return final


async def _index(slug: str, repo: Repo, sha: str) -> dict[str, Any]:
    """Every path under the tree `sha`: one recursive listing from GitHub per tree, kept on disk by the tree's hash
    like the other trees. {"truncated": GitHub cut the listing short, "paths": [[path, type], ...]}."""
    if not HASH_RE.fullmatch(sha):              # never a file name otherwise
        raise _Away("bad_answer")
    mem = _indexes.get(slug)
    if mem is not None and mem[0] == sha:
        return mem[1]
    folder = _cache_dir(slug)
    path = folder / f"{sha}.index"
    got = await anyio.to_thread.run_sync(_load_index, path)
    if got is None:
        async with _fetch_lock(f"{slug}/{sha}.index"):
            got = await anyio.to_thread.run_sync(_load_index, path)
            if got is None:
                st = _state(slug, repo)
                headers = await _auth(slug, repo, st)
                r = await _get(f"{config.get().github_api_url}/repos/{repo.owner}/{repo.name}/git/trees/{sha}"
                               f"?recursive=1", headers)
                try:
                    _check(r)
                except _Refused:
                    if r.status_code == 401:
                        st.token = None
                    raise _Missing(_reason(r)) from None
                answer = _json(r)
                got = {"truncated": bool(answer.get("truncated")), "paths": _index_entries(answer.get("tree"))}
                written = await anyio.to_thread.run_sync(_save_index, folder, sha, got)
                await anyio.to_thread.run_sync(evict, cache_root(), _limit(), written)
    _indexes[slug] = (sha, got)
    return got


def _find_limit(raw: Any) -> int:
    if raw is None or raw == "":
        return FIND_DEFAULT
    n = int(raw) if isinstance(raw, str) and re.fullmatch(r"\d{1,4}", raw.strip()) else None
    if n is None or not 1 <= n <= FIND_MOST:
        raise bad_request("invalid_limit", f"limit must be a whole number from 1 to {FIND_MOST}.")
    return n


async def find(slug: str, address: str, q: Any, raw_limit: Any) -> dict[str, Any]:
    """The files and folders of the head whose path holds every word of `q`, ignoring case, the shortest paths
    first. `complete` is false when GitHub listed the repository only in part."""
    if not isinstance(q, str) or not q.strip() or len(q) > FIND_Q_MOST:
        raise bad_request("invalid_query", f"q must be 1 to {FIND_Q_MOST} characters: words that the path contains.")
    limit = _find_limit(raw_limit)
    words = q.casefold().split()
    repo = _repo_of(address)

    async def work(h: Head):
        return h, await _index(slug, repo, h.tree)
    (h, index), _ = await _guarded(slug, repo, work)
    hits = [(p, kind) for p, kind in index["paths"] if all(w in p.casefold() for w in words)]
    hits.sort(key=lambda x: (len(x[0]), x[0]))
    return {"ref": h.ref, "commit": h.commit, "paths": [{"path": p, "type": kind} for p, kind in hits[:limit]],
            "complete": not index.get("truncated")}


async def stream(f, size: int) -> AsyncIterator[bytes]:
    """The bytes of an open file, read in a worker thread, closed at the end."""
    try:
        left = size
        while left > 0:
            chunk = await anyio.to_thread.run_sync(f.read, min(CHUNK, left))
            if not chunk:
                break
            left -= len(chunk)
            yield chunk
    finally:
        f.close()


def headers_for(ctype: str) -> dict[str, str]:
    """The headers every answer of the raw endpoint carries."""
    pdf = ctype == "application/pdf"
    return {"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": CSP_PDF if pdf else CSP_SANDBOX,
            # The page shows a PDF in a frame of its own origin; everything else is never framed.
            "X-Frame-Options": "SAMEORIGIN" if pdf else "DENY"}
