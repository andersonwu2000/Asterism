"""Acceptance tests for slice 1d, the server's side: reading the project's repository from GitHub, read-only.

A stand-in for GitHub's API runs on localhost and the server is pointed at it (ASTERISM_GITHUB_API_URL). It holds
one repository in memory, answers only the endpoints the contract names, checks the app's signed token as GitHub
does, and writes down every request it gets.

    python -m pytest tests/test_m1d.py -q
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import shutil
import threading
import time
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from test_m1b import ENV, SLUG, Person, build_world, free_port, until

APP_ID = "424242"
INSTALLATION = 77
REFRESH_S, CACHE_MB, MAX_MB = 2, 1, 1
OWNER_REPO = "example/lab"          # build_world makes the project with https://github.com/example/lab


def sha(*parts: bytes) -> str:
    return hashlib.sha1(b"\x00".join(parts)).hexdigest()


class FakeGitHub:
    """One repository, `main` only. `files` maps a path to its bytes; `commit()` makes them the head."""

    def __init__(self, public_key=None):
        self.public_key = public_key
        self.files: dict[str, bytes] = {}
        self.installed, self.public, self.down = True, False, False
        self.requests: list[tuple[str, str]] = []
        self.unauthenticated = 0
        self.tokens: list[str] = []
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, list[dict]] = {}
        self.recursive, self.truncate_after = 0, 0
        self.user_tokens: dict[str, dict] = {}         # a person's token -> {"login", "push"}
        self.writes: list[dict] = []                   # files written through the contents API
        self.install_writes = 0                        # writes tried with an installation token (must stay 0)      # recursive listings asked for; cut them after n entries
        self.head = ("", "")
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, status, body, ctype="application/json"):
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _app(self) -> bool:
                """The request carries the app's own token, signed as GitHub requires."""
                auth = self.headers.get("authorization") or ""
                try:
                    head, payload, sig = auth.split(" ", 1)[1].split(".")
                    pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
                    claims = json.loads(pad(payload))
                    assert json.loads(pad(head))["alg"] == "RS256"
                    fake.public_key.verify(pad(sig), f"{head}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
                    now = time.time()
                    return str(claims["iss"]) == APP_ID and claims["exp"] > now and claims["exp"] - claims["iat"] <= 660
                except Exception:
                    return False

            def _handle(self, method):
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length) if length else b""
                path = self.path.split("?")[0]
                fake.requests.append((method, path))
                if fake.down:
                    return self._send(503, {"message": "Service unavailable"})
                if path == f"/app/installations/{INSTALLATION}/access_tokens" and method == "POST":
                    if not self._app() or not fake.installed:
                        return self._send(401, {"message": "A JSON web token could not be decoded"})
                    token = f"ghs_{len(fake.tokens) + 1}"
                    fake.tokens.append(token)
                    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))
                    return self._send(201, {"token": token, "expires_at": expires})
                base = f"/repos/{OWNER_REPO}"
                user = fake.user_tokens.get((self.headers.get("authorization") or "").split(" ")[-1])
                if method == "PUT" and path.startswith(base + "/contents/"):
                    return self._put_contents(path[len(base + "/contents/"):], raw, user)
                if method != "GET":
                    return self._send(404, {"message": "Not Found"})
                if path == base and user is not None:
                    return self._send(200, {"full_name": OWNER_REPO, "default_branch": "main", "private": not fake.public,
                                            "permissions": {"pull": True, "push": user["push"], "admin": False}})
                if path == base + "/installation":
                    if not self._app():
                        return self._send(401, {"message": "A JSON web token could not be decoded"})
                    return self._send(200, {"id": INSTALLATION}) if fake.installed else self._send(404, {"message": "Not Found"})
                if not path.startswith(base):
                    return self._send(404, {"message": "Not Found"})
                auth = (self.headers.get("authorization") or "").split(" ")[-1]
                if auth not in fake.tokens:
                    fake.unauthenticated += 1
                    if not fake.public:
                        return self._send(404, {"message": "Not Found"})
                rest = path[len(base):]
                commit, root = fake.head
                if rest == "":
                    return self._send(200, {"full_name": OWNER_REPO, "default_branch": "main", "private": not fake.public})
                if rest == "/branches/main":
                    return self._send(200, {"name": "main", "commit": {"sha": commit, "commit": {"tree": {"sha": root}}}})
                if rest.startswith("/git/trees/"):
                    tree = fake.trees.get(rest.rsplit("/", 1)[1])
                    if tree is None:
                        return self._send(404, {"message": "Not Found"})
                    if "recursive=" in self.path:
                        fake.recursive += 1
                        flat, todo = [], [("", tree)]
                        while todo:
                            prefix, entries = todo.pop(0)
                            for x in entries:
                                flat.append(dict(x, path=prefix + x["path"]))
                                if x["type"] == "tree":
                                    todo.append((prefix + x["path"] + "/", fake.trees[x["sha"]]))
                        cut = fake.truncate_after
                        return self._send(200, {"sha": rest.rsplit("/", 1)[1], "tree": flat[:cut] if cut else flat,
                                                "truncated": bool(cut and len(flat) > cut)})
                    return self._send(200, {"sha": rest.rsplit("/", 1)[1], "tree": tree, "truncated": False})
                if rest.startswith("/git/blobs/"):
                    blob = fake.blobs.get(rest.rsplit("/", 1)[1])
                    if blob is None:
                        return self._send(404, {"message": "Not Found"})
                    if "raw" in (self.headers.get("accept") or ""):
                        return self._send(200, blob, "application/octet-stream")
                    return self._send(200, {"sha": rest.rsplit("/", 1)[1], "size": len(blob), "encoding": "base64",
                                            "content": base64.b64encode(blob).decode()})
                return self._send(404, {"message": "Not Found"})

            def _put_contents(self, file_path, raw, user):
                """GitHub's contents API: a user's token with push permission writes one file; an installation
                token is refused (the server must never write with it)."""
                auth = (self.headers.get("authorization") or "").split(" ")[-1]
                if auth in fake.tokens:
                    fake.install_writes += 1
                    return self._send(403, {"message": "Resource not accessible by integration"})
                if user is None:
                    return self._send(401, {"message": "Bad credentials"})
                if not user["push"]:
                    return self._send(404, {"message": "Not Found"})
                body = json.loads(raw or b"{}")
                current = fake.files.get(file_path)
                current_sha = sha(b"blob", current) if current is not None else None
                if current is not None and body.get("sha") != current_sha:
                    return self._send(409, {"message": f"{file_path} does not match {body.get('sha')}"})
                if current is None and body.get("sha"):
                    return self._send(404, {"message": "Not Found"})
                data = base64.b64decode(body["content"])
                fake.files[file_path] = data
                fake.commit()
                fake.writes.append({"path": file_path, "login": user["login"], "message": body.get("message"),
                                    "branch": body.get("branch")})
                return self._send(200 if current is not None else 201,
                                  {"content": {"path": file_path, "sha": sha(b"blob", data)},
                                   "commit": {"sha": fake.head[0]}})

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def do_PUT(self):
                self._handle("PUT")

            def do_PATCH(self):
                self._handle("PATCH")

            def do_DELETE(self):
                self._handle("DELETE")

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def commit(self):
        """Make `files` the head of main: blobs and one tree per folder, as GitHub lists them."""
        def tree_of(prefix: str) -> str:
            entries, seen = [], set()
            for path, data in sorted(self.files.items()):
                if not path.startswith(prefix):
                    continue
                name, _, more = path[len(prefix):].partition("/")
                if name in seen:
                    continue
                seen.add(name)
                if more:
                    entries.append({"path": name, "mode": "040000", "type": "tree", "sha": tree_of(prefix + name + "/")})
                else:
                    b = sha(b"blob", data)
                    self.blobs[b] = data
                    entries.append({"path": name, "mode": "100644", "type": "blob", "sha": b, "size": len(data)})
            t = sha(b"tree", json.dumps(entries, sort_keys=True).encode())
            self.trees[t] = entries
            return t
        root = tree_of("")
        self.head = (sha(b"commit", root.encode(), str(time.time()).encode()), root)

    def count(self, piece: str) -> int:
        return len([1 for _, p in self.requests if piece in p])

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


BIG = b"A" * 450_000
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
CONTENT = {
    "README.md": "# Test Lab\n".encode(),
    "notes/MAP.md": "# 研究圖景\n\nSee $x^2$ and `notes/lemma32.md`.\n".encode(),
    "notes/lemma32.md": b"# Lemma 3.2\n",
    "notes/Zeta.md": b"z\n",
    "notes/alpha.md": b"a\n",
    "notes/deep/inner/leaf.txt": b"leaf\n",
    "paper/main.tex": b"\\documentclass{article}\n",
    "paper/main.pdf": b"%PDF-1.4\n%fake\n",
    "paper/page.html": b"<script>alert(1)</script>",
    "figures/dot.png": PNG,
    "figures/mark.svg": b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    "Lab/Lemma32.lean": b"theorem t : True := trivial\n",
    "data/blob.bin": bytes(range(256)) * 4,
    "data/a.dat": BIG,
    "data/b.dat": BIG.replace(b"A", b"B"),
    "data/c.dat": BIG.replace(b"A", b"C"),
    "data/huge.dat": b"H" * 1_200_000,
}


def start(tmp: Path, hub: FakeGitHub, key_pem: bytes | None, **more):
    env = dict(ENV, ASTERISM_GITHUB_API_URL=hub.url, ASTERISM_FILES_REFRESH_S=str(REFRESH_S),
               ASTERISM_FILES_CACHE_MB=str(CACHE_MB), ASTERISM_FILES_MAX_MB=str(MAX_MB), **more)
    if key_pem is not None:
        (tmp / "app.pem").write_bytes(key_pem)
        env.update(ASTERISM_GITHUB_APP_ID=APP_ID, ASTERISM_GITHUB_APP_KEY=str(tmp / "app.pem"))
    data = tmp / "data"
    data.mkdir()
    world = build_world(data, env)
    world.data = data
    return world


def new_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                            serialization.NoEncryption())
    return key.public_key(), pem


@pytest.fixture(scope="module")
def d(tmp_path_factory):
    """A private repository that the app is installed on; alice owns the project, bob and carol are members."""
    public, pem = new_key()
    hub = FakeGitHub(public)
    hub.files = dict(CONTENT)
    hub.commit()
    world = start(tmp_path_factory.mktemp("d"), hub, pem)
    world.hub = hub
    yield world
    world.srv.stop()
    hub.stop()


def listing(person: Person, folder: str = "") -> httpx.Response:
    return person.c.get(f"/{SLUG}/api/files/list", params={"dir": folder})


def raw(person: Person, path: str, **headers) -> httpx.Response:
    return person.c.get(f"/{SLUG}/api/files/raw/{path}", headers=headers)


def err(r: httpx.Response) -> str:
    return r.json().get("error", "")


def cache_bytes(world) -> int:
    root = world.data / "cache"
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) if root.exists() else 0


# ------------------------------------------------------------------ reading

def test_a_member_browses_the_repository(d):
    r = listing(d.bob)
    assert r.status_code == 200, r.text
    root = r.json()
    assert (root["ref"], root["dir"], root["commit"]) == ("main", "", d.hub.head[0]) and not root.get("stale")
    assert [(e["name"], e["type"]) for e in root["entries"]] == [
        ("data", "dir"), ("figures", "dir"), ("Lab", "dir"), ("notes", "dir"), ("paper", "dir"), ("README.md", "file")], \
        "folders first, then files, each by name without regard to case"
    assert root["entries"][-1] == {"name": "README.md", "path": "README.md", "type": "file", "size": len(CONTENT["README.md"])}
    notes = listing(d.bob, "notes").json()
    assert [e["name"] for e in notes["entries"]] == ["deep", "alpha.md", "lemma32.md", "MAP.md", "Zeta.md"]
    assert notes["entries"][0] == {"name": "deep", "path": "notes/deep", "type": "dir"}
    assert [e["path"] for e in listing(d.bob, "notes/deep/inner/").json()["entries"]] == ["notes/deep/inner/leaf.txt"]
    assert listing(d.bob, "no/such").status_code == 404 and listing(d.bob, "README.md").status_code == 404
    assert listing(d.bob, "../etc").status_code in (400, 404)

    r = raw(d.bob, "notes/MAP.md")
    assert r.status_code == 200 and r.content == CONTENT["notes/MAP.md"]
    assert r.headers["content-type"] == "text/plain; charset=utf-8" and r.headers["x-content-type-options"] == "nosniff"
    tag = r.headers["etag"]
    assert raw(d.bob, "notes/MAP.md", **{"If-None-Match": tag}).status_code == 304
    assert raw(d.bob, "notes").status_code == 404 and raw(d.bob, "notes/nope.md").status_code == 404
    for sneaky in ("notes/%2e%2e/README.md", "notes%2f..%2fREADME.md", "notes%5cMAP.md", "%2e%2e/%2e%2e/etc/passwd"):
        assert raw(d.bob, sneaky).status_code in (400, 404), f"{sneaky}: a path never leaves the repository"

    r = d.bob.c.post(f"/{SLUG}/api/files/resolve", json={"paths": ["notes/MAP.md", "notes", "Lab/Lemma32.lean", "nope.md",
                                                                 "../x", "notes/map.md", ""]})
    assert r.status_code == 200 and r.json() == {"found": {"notes/MAP.md": "file", "notes": "dir", "Lab/Lemma32.lean": "file"}}, \
        "only what is there, by its exact name"
    assert d.bob.c.post(f"/{SLUG}/api/files/resolve", json={"paths": ["a"] * 201}).status_code == 400


def test_each_kind_of_file_is_served_as_what_it_is(d):
    kinds = {"paper/main.tex": "text/plain; charset=utf-8", "Lab/Lemma32.lean": "text/plain; charset=utf-8",
             "paper/main.pdf": "application/pdf", "figures/dot.png": "image/png", "figures/mark.svg": "image/svg+xml",
             "paper/page.html": "text/plain; charset=utf-8", "notes/deep/inner/leaf.txt": "text/plain; charset=utf-8"}
    for path, kind in kinds.items():
        r = raw(d.alice, path)
        assert r.status_code == 200 and r.content == CONTENT[path] and r.headers["content-type"] == kind, path
        assert r.headers["x-content-type-options"] == "nosniff", path
    assert "sandbox" in raw(d.alice, "figures/mark.svg").headers["content-security-policy"], "a picture that cannot act"
    assert "sandbox" in raw(d.alice, "paper/page.html").headers["content-security-policy"]
    pdf = raw(d.alice, "paper/main.pdf").headers.get("content-security-policy", "")
    assert "sandbox" not in pdf and "frame-ancestors 'self'" in pdf, "the page shows a PDF in a frame of its own"
    r = raw(d.alice, "data/blob.bin")
    assert r.status_code == 200 and r.headers["content-type"] == "application/octet-stream"
    assert "attachment" in r.headers.get("content-disposition", ""), "what cannot be shown is offered as a download"
    r = raw(d.alice, "data/huge.dat")
    assert r.status_code == 413 and err(r) == "too_large" and "github.com/example/lab" in r.json()["message"]


def test_only_members_read_and_nobody_writes(d):
    assert httpx.get(f"{d.srv.url}/{SLUG}/api/files/list").status_code == 401
    assert httpx.get(f"{d.srv.url}/{SLUG}/api/files/raw/README.md").status_code == 401
    outsider = Person(d.srv, "dave")
    assert listing(outsider).status_code in (403, 404) and raw(outsider, "README.md").status_code in (403, 404)
    assert outsider.c.post(f"/{SLUG}/api/files/resolve", json={"paths": ["README.md"]}).status_code in (403, 404)
    assert listing(d.carol).status_code == 200, "a member reads, whether or not GitHub knows them"
    for method in ("post", "put", "delete"):
        r = getattr(d.alice.c, method)(f"/{SLUG}/api/files/raw/README.md")
        assert r.status_code in (403, 404, 405), f"{method}: there is nothing to write through"
    writes = [(m, p) for m, p in d.hub.requests if m != "GET"]
    assert writes and all(m == "POST" and p == f"/app/installations/{INSTALLATION}/access_tokens" for m, p in writes), writes
    assert len(d.hub.tokens) <= 2, "the app's token for the repository is kept while it is good"
    allowed = ("/repos/example/lab", "/app/installations/")
    assert all(p.startswith(allowed) for _, p in d.hub.requests), "only the endpoints the contract names"


# ------------------------------------------------------------------ keeping up, and the cache

def test_a_push_shows_within_the_refresh_time(d):
    before = listing(d.alice).json()["commit"]
    d.hub.files["notes/MAP.md"] = "# 研究圖景，第二版\n".encode()
    d.hub.files["notes/new.md"] = b"new\n"
    del d.hub.files["notes/Zeta.md"]
    d.hub.commit()
    assert until(lambda: listing(d.alice).json()["commit"] == d.hub.head[0], REFRESH_S + 4), "the new head is seen"
    assert listing(d.alice).json()["commit"] != before
    names = [e["name"] for e in listing(d.alice, "notes").json()["entries"]]
    assert "new.md" in names and "Zeta.md" not in names
    assert raw(d.alice, "notes/MAP.md").content == d.hub.files["notes/MAP.md"]
    assert raw(d.alice, "notes/Zeta.md").status_code == 404
    assert raw(d.alice, "README.md").content == CONTENT["README.md"], "what did not change is as it was"


def test_what_was_fetched_is_not_fetched_again(d):
    raw(d.alice, "Lab/Lemma32.lean")
    listing(d.alice, "Lab")
    time.sleep(REFRESH_S + 0.5)
    listing(d.alice)                                        # the head is looked at again now
    seen = len(d.hub.requests)
    blob = d.hub.count("/git/blobs/")
    for _ in range(5):                                      # inside the refresh time: GitHub is not asked at all
        assert listing(d.alice, "Lab").status_code == 200 and raw(d.alice, "Lab/Lemma32.lean").status_code == 200
    assert len(d.hub.requests) == seen
    time.sleep(REFRESH_S + 0.5)
    assert raw(d.alice, "Lab/Lemma32.lean").status_code == 200 and listing(d.alice, "Lab").status_code == 200
    assert d.hub.count("/git/blobs/") == blob, "an unchanged file is never downloaded twice"
    assert len(d.hub.requests) <= seen + 2, "after the refresh time only the head is asked for"


def test_the_cache_can_be_thrown_away_and_stays_under_its_limit(d):
    assert raw(d.alice, "notes/lemma32.md").content == CONTENT["notes/lemma32.md"]
    assert (d.data / "cache").is_dir() and cache_bytes(d) > 0
    blobs = d.hub.count("/git/blobs/")
    shutil.rmtree(d.data / "cache")
    assert raw(d.alice, "notes/lemma32.md").content == CONTENT["notes/lemma32.md"], "fetched again, the same"
    assert listing(d.alice, "notes").status_code == 200
    assert d.hub.count("/git/blobs/") == blobs + 1

    for name in ("a", "b", "c"):                            # 450 kB each against a limit of 1 MB
        assert raw(d.alice, f"data/{name}.dat").content == CONTENT[f"data/{name}.dat"]
        assert cache_bytes(d) <= CACHE_MB * 1024 * 1024, f"after {name}: the cache is over its limit"
    asked = d.hub.count("/git/blobs/")
    assert raw(d.alice, "data/c.dat").status_code == 200 and d.hub.count("/git/blobs/") == asked, "the newest is kept"
    assert raw(d.alice, "data/a.dat").content == CONTENT["data/a.dat"]
    assert d.hub.count("/git/blobs/") == asked + 1, "the one used longest ago was dropped, and comes back when asked for"


def test_when_github_is_away_what_is_cached_still_shows(d):
    d.hub.files["fresh/never-read.md"] = b"nobody opened this yet" + bytes([10])
    d.hub.commit()
    assert until(lambda: listing(d.alice).json()["commit"] == d.hub.head[0], REFRESH_S + 4)
    assert raw(d.alice, "README.md").status_code == 200 and listing(d.alice, "paper").status_code == 200
    d.hub.down = True
    try:
        time.sleep(REFRESH_S + 0.5)
        r = listing(d.alice, "paper")
        assert r.status_code == 200 and r.json()["stale"] is True, "the last known tree, marked as possibly old"
        assert raw(d.alice, "README.md").content == CONTENT["README.md"], "and what was read before"
        r = raw(d.alice, "fresh/never-read.md")
        assert r.status_code == 502 and err(r) == "github_unavailable", "what was never fetched cannot be shown now"
        assert listing(d.alice, "fresh").status_code == 502
    finally:
        d.hub.down = False
    assert until(lambda: listing(d.alice).json().get("stale") is not True, REFRESH_S + 4), "and it recovers by itself"
    assert raw(d.alice, "fresh/never-read.md").status_code == 200


# ------------------------------------------------------------------ not connected, and public repositories

def test_a_private_repository_the_app_is_not_installed_on(tmp_path):
    public, pem = new_key()
    hub = FakeGitHub(public)
    hub.files = dict(CONTENT)
    hub.commit()
    hub.installed = False
    w = start(tmp_path, hub, pem)
    try:
        for r in (listing(w.alice), raw(w.alice, "README.md"),
                  w.alice.c.post(f"/{SLUG}/api/files/resolve", json={"paths": ["README.md"]})):
            assert r.status_code == 409 and err(r) == "not_connected", r.text
        assert "example/lab" in listing(w.alice).json()["message"], "the sentence names the repository"
        hub.installed = True                                # the owner installs the app
        assert until(lambda: listing(w.alice).status_code == 200, REFRESH_S + 5), "and the files appear without a restart"
    finally:
        w.srv.stop()
        hub.stop()


def test_a_public_repository_needs_no_app(tmp_path):
    hub = FakeGitHub()
    hub.files = dict(CONTENT)
    hub.commit()
    hub.public = True
    w = start(tmp_path, hub, None)
    try:
        assert [e["name"] for e in listing(w.bob).json()["entries"]][-1] == "README.md"
        assert raw(w.bob, "notes/MAP.md").content == CONTENT["notes/MAP.md"]
        assert hub.tokens == [] and hub.unauthenticated > 0 and all(m == "GET" for m, _ in hub.requests)
        hub.public = False                                  # it is made private, and no app is set up
        assert until(lambda: listing(w.bob, "paper").status_code == 409, REFRESH_S + 5)
    finally:
        w.srv.stop()
        hub.stop()
