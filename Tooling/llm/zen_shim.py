"""OpenCode Zen ⇄ codex CLI translation shim (Responses API), v3.

Measured facts this file answers (2026-08-21/22, free ox-alpha window):
  - Zen's `/responses` STREAM is nonconformant (only output_text.delta,
    no item lifecycle) — codex assembles zero output items. → the shim
    calls Zen NON-stream and synthesizes a conformant SSE sequence.
  - codex hard-injects a `web_search` tool type; Zen 500s on it. → drop.
  - Zen's prefix cache is POISONABLE (a failed generation reproduces on
    the same prefix). → per-request nonce in `instructions`.
  - codex packs every MCP server as ONE `namespace` tool and routes its
    calls only through the ChatGPT-side code-mode convention; ox-alpha
    never learned that convention (it calls flat names), and codex's
    router answers "unsupported call" forever. `code_mode_host = false`
    does NOT flatten (probed). → the shim FLATTENS namespaces for the
    model AND executes the flat `mcp__asterism_tools__*` calls ITSELF,
    in-process, iterating against Zen until the model yields output
    codex can digest. codex never sees a flat call.

Tool execution: `Tooling.knowledge.mcp_tools`'s tools are plain module
functions; the per-spawn context they need (the attempts dir, named by
the request URL) rides a request-local ContextVar
(`spawn_guard.ATTEMPT_DIR_CONTEXT`), so concurrent requests execute
tools in parallel without touching process env. (The former global
lock + env pin starved the whole fleet behind one 28-minute grep,
2026-08-23.)

Run:  python -m Tooling.llm.zen_shim [port]   (default 8898)
Key:  OPENCODE_ZEN_API_KEY env, or .env's OPENCODE_ZEN_API_KEY.
"""
from __future__ import annotations

import collections
import http.server
import io
import json
import os
import posixpath
import re
import select
import signal
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

# Upstream: OpenRouter by default (2026-08-22). Zen's gateway kills
# long generations ("Internal server error") and ignores the
# `reasoning.max_tokens` cap that CURES ox-alpha's runaway-reasoning
# pathology (unbounded thinking until max_tokens, content never
# written — measured on both gateways); OpenRouter honors it and also
# serves a conformant /responses. Model ids differ per gateway.
# Two upstreams (2026-08-22, owner call: the fleet cannot live on
# OpenRouter's 1000-requests/day free cap). Zen is PRIMARY via its
# /chat/completions endpoint — the free week's near-unlimited token
# quota, healthy in streaming with effort pinned (its /responses
# dialect is broken both ways: non-stream edge-killed at ~35s, stream
# drops tool-call arguments). OpenRouter stays as the RESCUE tier for
# Zen hiccups — 1000 requests/day is a useless primary but a fine
# parachute.
# 2026-08-22 (late): Nous Portal joined the free window
# (inference-api.nousresearch.com, "1 quadrillion tokens/day") and
# measured strictly better than Zen on every axis — 5/5 clean, long
# output 15s vs Zen's 53s, and even BARE long output finishes (the
# runaway that kills Zen without the effort pin does not appear).
# Nous is PRIMARY; OpenCode Zen stays the rescue tier.
ZEN = os.environ.get("ASTERISM_ZEN_UPSTREAM",
                     "https://inference-api.nousresearch.com/v1")
ZEN_RESCUE = os.environ.get("ASTERISM_ZEN_RESCUE",
                            "https://opencode.ai/zen/v1")


def _model_for(base: str, model: "str | None") -> "str | None":
    """The same brain wears a different name per gateway."""
    if model is None:
        return model
    if "openrouter" in base or "nousresearch" in base:
        return {"x-preview-f-free": "stealth/ox-alpha"}.get(model, model)
    return {"stealth/ox-alpha": "x-preview-f-free"}.get(model, model)
ZEN_EFFORT = os.environ.get("ASTERISM_ZEN_EFFORT", "medium")
NS = "mcp__asterism_tools"
LSP_NS = "mcp__lsp"
GATEWAY_MCP = os.environ.get("ASTERISM_GATEWAY_MCP",
                             "http://127.0.0.1:8765/mcp")
#: Iteration cap = runaway backstop only, NOT the work budget — the
#: seat wall caps bound total time and the pacer bounds call rate, so
#: this only has to stop an infinite ping-pong. 80 was arbitrary and
#: healthy validate→fix loops hit it 25 times in one day (2026-08-22);
#: 200 ≈ 50-80 min of tool work, inside every seat's wall budget. The
#: cap-10 warning and the wrap-up turn ride whatever the value is.
MAX_TOOL_ITERATIONS = int(
    os.environ.get("ASTERISM_ZEN_MAX_TOOL_ITERS") or 200)

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

def _log(msg: str) -> None:
    """Shim logs go to STDERR: the tool wrappers in mcp_tools capture
    sys.stdout process-wide (contextlib.redirect_stdout), and in this
    THREADED server one request's capture was swallowing every other
    thread's shim prints — the model received paper_search results
    that BEGAN with '[shim] iter 31: ...' (live, 2026-08-22)."""
    print(msg, file=sys.stderr)


# (the global _TOOL_LOCK died 2026-08-23 — request context rides a
# ContextVar now; see _run_tool.)
# Both separators: codex 0.147 rendered the skills-preamble paths with
# backslashes, 0.149 renders them with FORWARD slashes — the
# backslash-only pattern silently stopped matching after the upgrade,
# attempt_dir came back None, every write_file was refused, and the
# strategist declared its batch committed anyway (g629, 2026-08-22).
#
# Two absolute-path shapes, either separator style: `[A-Za-z]:[\\/]`
# (Windows drive) or a bare leading `/` (POSIX) — this fallback is a
# haystack scan over free-form request text, not an OS-native parse,
# so it must recognize whichever OS actually wrote the transcript
# (Oracle ARM64 readiness P0#4: the dispatcher writes real POSIX
# `.attempts` paths into the environment context on Linux, and the old
# Windows-only pattern left `attempt_dir=None` there — same failure
# mode as the backslash regression above). The trailing group captures
# nested projection dirs (`<uuid>/adversary/r2`) the same way
# `_channel_of_path`'s URL channel does.
_ATTEMPT_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|/)[^\s'\"]*\.attempts[\\/][0-9a-fA-F-]{36}"
    r"(?:[\\/][A-Za-z0-9_.-]+)*")


def _attempts_root_norm() -> str:
    """This workspace's `.attempts` root, forward-slash normalized.
    Computed fresh from `_REPO` on every call (not cached at import
    time) so tests can `monkeypatch.setattr(zen_shim, "_REPO", ...)`
    the same way `_channel_of_path`'s tests already do — a frozen
    module-level constant would silently keep validating against the
    real workspace after that patch."""
    return posixpath.normpath(
        os.path.join(_REPO, ".attempts").replace("\\", "/"))


def _fence_attempt_candidate(raw: str) -> "str | None":
    """Verify a regex-matched `.attempts/<uuid>[/...]` path actually
    resolves inside THIS workspace's `.attempts` tree; return the
    normalized path, or None to reject it.

    Deliberately does the `..`-collapse and containment check with
    `posixpath.normpath` on a forward-slash-normalized string rather
    than `pathlib.Path(raw).resolve()`: the regex now matches BOTH
    Windows drive paths and POSIX absolute paths regardless of which
    OS this process runs on, and a platform `Path` parses the "foreign"
    style as RELATIVE (no drive, or a backslash on POSIX is just a
    filename character) — silently defeating the fence instead of
    rejecting it. Loosening the regex must not loosen the read/write
    fence: a foreign tree or a `..` escape is rejected here even though
    it would now satisfy the pattern."""
    norm = posixpath.normpath(raw.replace("\\", "/"))
    root = _attempts_root_norm()
    if norm != root and not norm.startswith(root + "/"):
        return None
    return norm


_KEY_CACHE: "dict[str, str]" = {}


def _key_for(base: str) -> str:
    name = ("NOUS_API_KEY" if "nousresearch" in base
            else "OPENROUTER_API_KEY" if "openrouter" in base
            else "OPENCODE_ZEN_API_KEY")
    if name in _KEY_CACHE:
        return _KEY_CACHE[name]
    k = os.environ.get(name, "")
    if not k:
        env = os.path.join(_REPO, ".env")
        try:
            for line in open(env, encoding="utf-8"):
                if line.startswith(name + "="):
                    k = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
    if not k:
        raise SystemExit(f"no {name} (env or .env)")
    _KEY_CACHE[name] = k
    return k


def _tools_module():
    from Tooling.knowledge import mcp_tools  # heavy; import once, lazily
    return mcp_tools


#: Tool calls in flight: {thread id: (tool, scope, started_at)}. The
#: observability half of the 2026-08-23 stall fix — with the global
#: lock gone a wedged call no longer blocks the channel, so the "oldest
#: running call" age is how an individual leak is found.
_TOOLS_ACTIVE: "dict[int, tuple[str, str, float]]" = {}
_TOOLS_ACTIVE_LOCK = threading.Lock()


def _tools_snapshot() -> dict:
    now = time.time()
    with _TOOLS_ACTIVE_LOCK:
        running = [{"tool": n, "scope": s, "age_sec": round(now - t, 1)}
                   for n, s, t in _TOOLS_ACTIVE.values()]
    running.sort(key=lambda r: -r["age_sec"])
    with _CONC_LOCK:
        conc = {"cap": _CONC_CAP, "free": _CONC_FREE,
                "waiting": len(_CONC_WAITERS),
                "mode": "auto" if _CONC_AUTO else "pinned"}
    return {"tools_running": running,
            "oldest_tool_age_sec": running[0]["age_sec"] if running else 0,
            "upstream_slots": conc}


def _run_tool(name: str, args: dict, attempt_dir: "str | None") -> str:
    """Execute one in-process tool with REQUEST-LOCAL attempt-dir
    context. The former shape pinned a process-wide env var under a
    global lock; one 28-minute grep then starved all twelve spawns'
    tool calls while heartbeats froze (2026-08-23). The ContextVar
    isolates concurrent requests without serializing them — deleting
    the lock alone would have let agents read each other's attempt
    dirs, which is worse than the stall."""
    mod = _tools_module()
    fn = getattr(mod, name, None)
    if fn is None:
        return f"unknown tool {name!r}"
    from Tooling.llm.spawn_guard import ATTEMPT_DIR_CONTEXT
    tid = threading.get_ident()
    token = ATTEMPT_DIR_CONTEXT.set(attempt_dir or None)
    with _TOOLS_ACTIVE_LOCK:
        _TOOLS_ACTIVE[tid] = (name, json.dumps(args)[:120], time.time())
    try:
        try:
            return str(fn(**args))
        except TypeError as e:
            return f"bad arguments for {name}: {e}"
        except Exception as e:  # noqa: BLE001 — tool result surface
            return f"{name} raised {type(e).__name__}: {e}"
    finally:
        with _TOOLS_ACTIVE_LOCK:
            _TOOLS_ACTIVE.pop(tid, None)
        ATTEMPT_DIR_CONTEXT.reset(token)


_LSP_SESSIONS: dict = {}


def _mcp_http(payload: dict, headers: dict) -> "tuple[dict | None, dict]":
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        GATEWAY_MCP, data=data,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 **headers})
    with urllib.request.urlopen(req, timeout=1200) as r:
        # HTTP header names are case-insensitive but dict() keeps the
        # wire casing — uvicorn sends lowercase `content-type`, and a
        # `.get("Content-Type")` miss silently rerouted every SSE body
        # through the JSON branch (all LSP tools died "no parseable
        # response" for the fleet's whole first hour, 2026-08-22).
        # Normalize ONCE here; every caller looks up lowercase.
        resp_headers = {k.lower(): v for k, v in r.headers.items()}
        raw = r.read().decode("utf-8", "replace")
    if "event-stream" in str(resp_headers.get("content-type", "")):
        obj = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    obj = json.loads(line[5:])
                except ValueError:
                    pass
        return obj, resp_headers
    try:
        return json.loads(raw) if raw.strip() else None, resp_headers
    except ValueError:
        return None, resp_headers


def _lsp_session_for(attempt_dir: str) -> "tuple[str, str] | None":
    """(mcp_session_id, gateway_token) for this spawn, cached. The
    gateway's streamable-HTTP MCP wants an initialize handshake; the
    spawn's auth token sits in `<attempt_dir>/_gateway_session.token`
    (written by pipeline._write_mcp_config).

    The token is read fresh EVERY call and the cache holds only the
    handshake it produced: a permanent (sid, token) cache outlived both
    a rewritten token (retry spawns) and a gateway generation swap —
    and the shim is a detached long-liver now, so a poisoned entry
    used to answer "no session" for the rest of the run."""
    try:
        token = open(os.path.join(attempt_dir, "_gateway_session.token"),
                     encoding="utf-8").read().strip()
    except OSError:
        return None
    cached = _LSP_SESSIONS.get(attempt_dir)
    if cached and cached[1] == token:
        return cached
    hdr = {"X-Asterism-Session": token}
    obj, rh = _mcp_http({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2025-03-26",
                                    "capabilities": {},
                                    "clientInfo": {"name": "zen-shim",
                                                   "version": "5.0"}}},
                        hdr)
    sid = rh.get("mcp-session-id") or ""  # rh is lowercase-normalized
    if sid:
        hdr2 = {**hdr, "Mcp-Session-Id": sid}
        try:
            _mcp_http({"jsonrpc": "2.0",
                       "method": "notifications/initialized"}, hdr2)
        except Exception:  # noqa: BLE001 — some servers 202 this oddly
            pass
    _LSP_SESSIONS[attempt_dir] = (sid, token)
    return _LSP_SESSIONS[attempt_dir]


def _run_lsp_tool(name: str, args: dict, attempt_dir: "str | None") -> str:
    # The teaching names the way out: an agent whose Lean surface was
    # down used to hand-write a turn of unverified Lean and get bounced
    # at commit anyway (2026-08-22 ×2 — the commit gate held, the turn
    # was wasted). Failing fast IS the retry path.
    _down = (" — the Lean surface is unavailable this turn. Do NOT "
             "hand-write unverified Lean around it: end your turn now "
             "stating the surface was down; the framework retries the "
             "wake when it returns.")
    if not attempt_dir:
        return "lsp tools need a session; no attempts dir found" + _down
    sess = _lsp_session_for(attempt_dir)
    if sess is None:
        return "no _gateway_session.token in attempts dir" + _down
    # One re-handshake retry: an HTTP error or a JSON-RPC-level error
    # from tools/call is the session layer speaking (tool failures ride
    # inside `result`), and the cached sid is dead after a gateway
    # generation swap. Evict, shake hands again, retry ONCE.
    for attempt in (1, 2):
        sid, token = sess
        hdr = {"X-Asterism-Session": token}
        if sid:
            hdr["Mcp-Session-Id"] = sid
        try:
            obj, _ = _mcp_http({"jsonrpc": "2.0", "id": 2,
                                "method": "tools/call",
                                "params": {"name": name,
                                           "arguments": args}},
                               hdr)
        except urllib.error.HTTPError as e:
            _LSP_SESSIONS.pop(attempt_dir, None)
            if attempt == 1:
                sess = _lsp_session_for(attempt_dir)
                if sess is not None:
                    continue
            return f"lsp gateway HTTP {e.code}: {e.read()[:200]!r}"
        except Exception as e:  # noqa: BLE001 — tool result surface
            return f"lsp transport error: {e}"
        if not obj:
            return "lsp gateway returned no parseable response"
        if obj.get("error"):
            _LSP_SESSIONS.pop(attempt_dir, None)
            if attempt == 1:
                sess = _lsp_session_for(attempt_dir)
                if sess is not None:
                    continue
            return f"lsp error: {obj['error']}"
        result = obj.get("result") or {}
        parts = result.get("content") or []
        text = "".join(p.get("text", "") for p in parts
                       if isinstance(p, dict))
        return text or json.dumps(result)[:2000]
    return "lsp session could not be re-established"  # unreachable


def _attempt_dir_from_path(path: str) -> "str | None":
    """The deterministic channel: `/a/<relpath>/v1/...` names this
    spawn's attempts dir outright (per-spawn codex config, codex_cli).

    The segment is a PATH under `.attempts`, not a bare uuid: adversary
    and judge rounds spawn from projection dirs (`<uuid>/adversary/r2`),
    and a uuid-shaped parse missed them — every write in those legs was
    refused while the strategists' own writes landed (2026-08-22)."""
    return _channel_of_path(path)[0]


def _channel_of_path(path: str) -> "tuple[str | None, int | None]":
    """(attempts dir, turn time-budget seconds) named by the URL.

    `/a/<relpath>[/b/<sec>]/v1/...` — the optional `/b/` segment is the
    seat's wall budget minus a wrap-up margin, so the tool loop can
    finalize BEFORE the subprocess wall kills the turn (see codex_cli;
    the 200-iteration cap alone was unreachable inside a 1800s wall)."""
    m = re.match(r"^/a/(.+?)(?:/b/(\d+))?/v1(?:/|$)", path or "")
    if not m:
        return None, None
    budget = int(m.group(2)) if m.group(2) else None
    parts = m.group(1).split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None, None
    cand = os.path.join(_REPO, ".attempts", *parts)
    # The dispatcher creates the dir before the spawn, so a real
    # channel always names an existing dir; a miss means a stale
    # generation's config (basename-only URLs) — fall back to the
    # request-text archaeology rather than answer confidently wrong.
    return (cand if os.path.isdir(cand) else None), budget


def _attempt_dir_of(body: dict) -> "str | None":
    # Scan the WHOLE request: the 20K slice used here first let the
    # skills preamble push the environment context (which carries the
    # attempts dir) past the window — attempt_dir=None, every
    # write_file refused, agent_no_output (measured 2026-08-22).
    hay = json.dumps(body.get("instructions", "")) + json.dumps(
        body.get("input", ""))
    m = _ATTEMPT_RE.search(hay.replace("\\\\", "\\"))
    if not m:
        return None
    # The regex alone is not the fence: it now matches any absolute
    # path shaped like `.../.attempts/<uuid>[/...]`, POSIX or Windows,
    # so a foreign tree or a `..` escape embedded in agent-controlled
    # request text (tool output the model quoted back, a pasted error)
    # must still be rejected here rather than trusted as this spawn's
    # own attempts dir.
    return _fence_attempt_candidate(m.group(0))


def _dump_4xx(e: "urllib.error.HTTPError", body: dict) -> "urllib.error.HTTPError":
    """Full forensics on a deterministic client rejection, re-raising
    with the error body re-attached (the outer handler forwards it to
    codex verbatim). The 150-byte log line buried the diagnosis once
    (p143's strategist died agent_no_output on an unexplained
    `invalid_prompt`, 2026-08-22)."""
    err_bytes = e.read()
    try:
        dump = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", ".asterism", "logs",
            f"zen_shim_4xx_{int(time.time())}.json")
        with open(dump, "w", encoding="utf-8") as f:
            json.dump({"status": e.code,
                       "error": err_bytes.decode("utf-8", "replace"),
                       "request": body}, f, ensure_ascii=False, indent=1)
        _log(f"[shim] 4xx dumped -> {dump}")
    except Exception:  # noqa: BLE001 — dump is best-effort
        pass
    return urllib.error.HTTPError(
        e.url, e.code, e.reason, e.headers, io.BytesIO(err_bytes))


def _to_chat(body: dict) -> dict:
    """/responses request → /chat/completions request.

    Zen's /responses dialect is broken in both transports (non-stream:
    the edge kills >35s responses; stream: function_call arguments are
    never emitted and response.completed carries no output). Its
    /chat/completions endpoint is healthy in streaming — tool-call
    arguments flow, long text completes — PROVIDED `reasoning.effort`
    rides along (bare and max_tokens both leave the runaway uncured;
    all measured 2026-08-22)."""
    msgs: list = []
    if body.get("instructions"):
        msgs.append({"role": "system", "content": body["instructions"]})
    pending_calls: list = []

    def _flush_calls() -> None:
        if pending_calls:
            msgs.append({"role": "assistant", "content": None,
                         "tool_calls": list(pending_calls)})
            pending_calls.clear()

    for it in body.get("input") or []:
        if not isinstance(it, dict):
            _flush_calls()
            msgs.append({"role": "user", "content": str(it)})
            continue
        t = it.get("type")
        if t == "function_call":
            pending_calls.append(
                {"id": it.get("call_id") or it.get("id") or "",
                 "type": "function",
                 "function": {"name": it.get("name"),
                              "arguments": it.get("arguments") or "{}"}})
            continue
        _flush_calls()
        if t == "function_call_output":
            msgs.append({"role": "tool",
                         "tool_call_id": it.get("call_id") or "",
                         "content": str(it.get("output") or "")})
        elif t == "reasoning":
            continue
        else:  # message (or role-bearing item)
            role = it.get("role") or "user"
            parts = it.get("content")
            if isinstance(parts, list):
                text = "\n".join(
                    str(p.get("text", "")) for p in parts
                    if isinstance(p, dict)
                    and p.get("type") in ("input_text", "output_text",
                                          "text"))
            else:
                text = str(parts or "")
            msgs.append({"role": "assistant" if role == "assistant"
                         else "user", "content": text})
    _flush_calls()
    chat: dict = {"stream": True, "messages": msgs,
                  "reasoning": body.get("reasoning")
                  or {"effort": ZEN_EFFORT}}
    tools = [{"type": "function",
              "function": {"name": t.get("name"),
                           "description": t.get("description", ""),
                           "parameters": t.get("parameters") or {}}}
             for t in body.get("tools") or []
             if t.get("type") == "function"]
    if tools:
        chat["tools"] = tools
    return chat


def _chat_stream_once(base: str, body: dict) -> dict:
    """Streaming /chat/completions call, assembled back into a
    /responses-shaped response object so the shim's main loop stays in
    one vocabulary."""
    chat = _to_chat(body)
    chat["model"] = _model_for(base, body.get("model"))
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(chat, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + _key_for(base),
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream",
                 "User-Agent": "asterism-zen-shim/6.0"})
    text: list = []
    rsn: list = []
    calls: dict = {}
    usage: dict = {}
    finish = None
    # The socket timeout is ALSO the per-read (inter-chunk) limit: a
    # healthy generation streams deltas (reasoning included)
    # continuously, so 300s of silence is a dead stream, not a
    # thinking pause — two strategists sat 11+ minutes on stalled
    # Nous streams under the old 1740s ceiling (2026-08-22).
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            try:
                d = json.loads(line[5:])
            except ValueError:
                continue
            if d.get("usage"):
                usage = d["usage"]
            ch = (d.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            # The upstream streams the thinking phase alongside the
            # answer (`delta.reasoning`, OpenRouter dialect; some
            # providers spell it `reasoning_content`). Dropping it made
            # the zen seat the one black-box seat — generated and BILLED
            # either way, just invisible (owner call 2026-08-24).
            if delta.get("reasoning"):
                rsn.append(str(delta["reasoning"]))
            elif delta.get("reasoning_content"):
                rsn.append(str(delta["reasoning_content"]))
            if delta.get("content"):
                text.append(delta["content"])
            for tc in delta.get("tool_calls") or []:
                slot = calls.setdefault(
                    tc.get("index", len(calls)),
                    {"id": "", "name": "", "arguments": []})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                f = tc.get("function") or {}
                if f.get("name"):
                    slot["name"] = f["name"]
                if f.get("arguments"):
                    slot["arguments"].append(f["arguments"])
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
    if finish is None and not text and not calls:
        raise urllib.error.URLError("chat stream ended empty, no finish")
    items: list = []
    if rsn:
        # Responses-API reasoning item, FIRST (the order the native
        # OpenAI path uses). codex records it in the rollout jsonl —
        # ox-alpha's thinking lands in the same transcripts the
        # operator already reads for codex/claude seats. The round
        # trip is free: codex replays it in later turns' input, and
        # `_to_chat` already skips `type == "reasoning"` items, so the
        # text never flows back upstream and costs nothing.
        items.append({"type": "reasoning",
                      "id": "rs_" + uuid.uuid4().hex,
                      "summary": [{"type": "summary_text",
                                   "text": "".join(rsn)}]})
    if text:
        items.append({"type": "message", "role": "assistant",
                      "content": [{"type": "output_text",
                                   "text": "".join(text)}]})
    for i in sorted(calls):
        c = calls[i]
        cid = c["id"] or f"call_{uuid.uuid4().hex[:12]}"
        items.append({"type": "function_call", "name": c["name"],
                      "id": cid, "call_id": cid,
                      "arguments": "".join(c["arguments"]) or "{}"})
    # codex (0.149+) parses ResponseCompleted STRICTLY and rejects a
    # response missing fields one by one — usage.total_tokens killed
    # g618, `id` killed g623, each as "stream disconnected before
    # completion" -> rc=1 -> unclassified. Fix the CLASS: synthesize
    # the complete response envelope, not just the parts we consume.
    in_t = usage.get("prompt_tokens", usage.get("input_tokens")) or 0
    out_t = usage.get("completion_tokens", usage.get("output_tokens")) or 0
    usage_out: dict = {"input_tokens": in_t, "output_tokens": out_t,
                       "total_tokens": usage.get("total_tokens")
                       or (in_t + out_t)}
    # Pass the reasoning-token count through when the upstream reports
    # it (chat dialect: completion_tokens_details.reasoning_tokens) —
    # codex's token_count accounting reads output_tokens_details, which
    # sat at 0 while the thinking was being generated and billed.
    _rt = (usage.get("completion_tokens_details") or {}).get(
        "reasoning_tokens")
    if _rt is not None:
        usage_out["output_tokens_details"] = {"reasoning_tokens": _rt}
    return {"id": "resp_" + uuid.uuid4().hex,
            "object": "response",
            "created_at": int(time.time()),
            "model": chat["model"],
            "status": "completed",
            "output": items,
            "usage": usage_out}


def _stream_once(base: str, body: dict) -> dict:
    """One STREAMING /responses call; returns the final response object.

    Streaming is load-bearing, not a transport preference: Zen's edge
    kills a non-streaming response at ~35s, which we mis-filed as 'Zen
    cannot do long outputs' for two days — the same request with
    `stream: true` finishes fine (413-word essay, 59s, measured
    2026-08-22). On OpenRouter the last `response.completed` event
    carries the whole response object; Zen's /responses stream is
    broken (drops function-call arguments, empty completed) so the
    Zen leg goes through /chat/completions instead."""
    if "openrouter" not in base:
        return _chat_stream_once(base, body)
    b = dict(body)
    b["model"] = _model_for(base, b.get("model"))
    b["stream"] = True
    req = urllib.request.Request(
        base + "/responses",
        data=json.dumps(b, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + _key_for(base),
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream",
                 "User-Agent": "asterism-zen-shim/6.0"})
    # The socket timeout is ALSO the per-read (inter-chunk) limit: a
    # healthy generation streams deltas (reasoning included)
    # continuously, so 300s of silence is a dead stream, not a
    # thinking pause — two strategists sat 11+ minutes on stalled
    # Nous streams under the old 1740s ceiling (2026-08-22).
    with urllib.request.urlopen(req, timeout=300) as r:
        final: "dict | None" = None
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                d = json.loads(line[5:])
            except ValueError:
                continue
            if d.get("type") == "response.completed":
                final = d.get("response")
            elif d.get("type") == "response.failed":
                raise urllib.error.URLError(
                    f"upstream response.failed: "
                    f"{json.dumps(d)[:300]}")
    if final is None:
        raise urllib.error.URLError("stream ended without "
                                    "response.completed")
    return final


#: Alternating upstream schedule. Peak-hour Zen answers EMPTY
#: stochastically (22 hits in 15 fleet-minutes, 2026-08-22 06:20 local),
#: so three tries is a coin flip while eight is near-certain; and the
#: rescue's own 429 (daily cap spent, resets 00:00 UTC) must NOT kill
#: the request — a dead parachute sends us back to hammering Zen, not
#: to the ground. Strategists died quota_exhausted through exactly that
#: chain (Zen empty ×3 → rescue 429 → propagate) before this schedule.
#: Client-side pacing to the primary's known window (Nous free tier:
#: 50 req/min rolling). Paced at 40 to leave margin for the request the
#: window counts that we do not see (a second machine on the same key
#: produced an 864-retry storm, 2026-08-22). 0 disables.
_RPM = int(os.environ.get("ASTERISM_ZEN_RPM") or 40)
_PACE_LOCK = threading.Lock()
_PACE_STAMPS: "collections.deque[float]" = collections.deque()


def _pace() -> None:
    """Take one slot in the rolling window, sleeping until one frees.

    Pacing is the root-cause half of 429 handling: with the client
    holding itself to the known budget, a 429 is contention from
    OUTSIDE (another machine on the key) rather than our own burst —
    rare instead of chronic. The wait half lives in `_zen_call`."""
    if _RPM <= 0:
        return
    while True:
        with _PACE_LOCK:
            now = time.monotonic()
            while _PACE_STAMPS and now - _PACE_STAMPS[0] > 60:
                _PACE_STAMPS.popleft()
            if len(_PACE_STAMPS) < _RPM:
                _PACE_STAMPS.append(now)
                return
            wait = 60.0 - (now - _PACE_STAMPS[0]) + 0.05
        time.sleep(min(wait, 5.0))


#: Concurrent upstream inference requests. The 2026-08-22 storm's true
#: cause (friend-machine probe): Nous throttles CONCURRENCY for
#: low-credit accounts — six tiny simultaneous requests all 429'd
#: ("Too many concurrent inference requests for an account with low
#: available credits") while the per-minute headers sat nearly full,
#: so RPM pacing treats the wrong variable. The semaphore is the
#: matching choke point: excess requests queue here, orderly, instead
#: of burning 429 retries upstream.
#:
#: 2026-08-24 (Nous Portal subscription): the account's concurrency
#: limit is a SUBSCRIPTION property — 5 was the wall before, a 96-way
#: probe ran clean the day the owner subscribed. A hand-pinned number
#: drifts the day the plan changes, so the default is ADAPTIVE (AIMD):
#: halve on the upstream's own concurrency-429 verdict (its body names
#: the fired limit; window/capacity 429s never shrink), grow by one
#: only while calls actually queue and the window has been clean.
#: Set ASTERISM_ZEN_CONCURRENCY to pin the cap by hand (old
#: semantics; 0 disables the gate entirely).
_CONC_PIN = (os.environ.get("ASTERISM_ZEN_CONCURRENCY") or "").strip()
_CONC_AUTO = not _CONC_PIN
_CONC_FLOOR = 2          # adaptive never starves the fleet below this
_CONC_CEILING = int(os.environ.get("ASTERISM_ZEN_CONC_CEILING") or 128)
_CONC_START = 5          # last empirically safe pre-subscription cap
_CONC_SHRINK_COOLDOWN = 300.0  # no upward probe this long after a shrink
_CONC_GROW_INTERVAL = 60.0     # at most one +1 per this many seconds
_CONCURRENCY = int(_CONC_PIN) if _CONC_PIN else _CONC_START
#: FIFO with DIRECT HANDOFF, not a bare semaphore: the first cut used
#: `acquire(timeout=5)` polling, and a poller that times out re-joins
#: at the back — spawns mid-iteration re-acquired instantly and
#: starved the queued ones for 30+ minutes while their queue-side
#: heartbeats dressed the starvation up as liveness (caught by the
#: operator noticing "no files written", 2026-08-22).
_CONC_LOCK = threading.Lock()
_CONC_WAITERS: "collections.deque[threading.Event]" = collections.deque()
_CONC_CAP = max(_CONCURRENCY, 1)
_CONC_FREE = _CONC_CAP
_CONC_LAST_SHRINK = 0.0
#: import-time stamp: the first upward probe waits out one full
#: interval of REAL gated traffic — a cold process never bursts.
_CONC_LAST_GROW = time.time()


def _conc_enabled() -> bool:
    return _CONC_AUTO or _CONCURRENCY > 0


def _conc_acquire(attempt_dir: "str | None") -> None:
    ev: "threading.Event | None" = None
    with _CONC_LOCK:
        global _CONC_FREE
        if _CONC_FREE > 0 and not _CONC_WAITERS:
            _CONC_FREE -= 1
            return
        ev = threading.Event()
        _CONC_WAITERS.append(ev)
    waited = 0
    while not ev.wait(timeout=5):
        waited += 5
        _touch_heartbeat(attempt_dir)
        if waited % 60 == 0:
            _log(f"[shim]   queue: {waited}s waiting for a "
                  f"concurrency slot ({len(_CONC_WAITERS)} in line)")


def _conc_release() -> None:
    with _CONC_LOCK:
        global _CONC_FREE, _CONC_CAP, _CONC_LAST_GROW
        now = time.time()
        # Additive increase — only under REAL demand (a queue exists),
        # never inside a shrink's cooldown, at most one step per
        # interval. An idle gate never probes upward.
        if (_CONC_AUTO and _CONC_WAITERS and _CONC_CAP < _CONC_CEILING
                and now - _CONC_LAST_SHRINK > _CONC_SHRINK_COOLDOWN
                and now - _CONC_LAST_GROW > _CONC_GROW_INTERVAL):
            _CONC_CAP += 1
            _CONC_FREE += 1
            _CONC_LAST_GROW = now
            _log(f"[shim]   gate +1 → {_CONC_CAP} "
                  f"({len(_CONC_WAITERS)} in line, window clean)")
        if _CONC_FREE < 0:
            _CONC_FREE += 1  # repay a shrink's debt before anyone runs
        elif _CONC_WAITERS:
            _CONC_WAITERS.popleft().set()  # the slot passes head-first
        else:
            _CONC_FREE += 1
        # a grow above freed an EXTRA slot — hand it to the queue too
        while _CONC_FREE > 0 and _CONC_WAITERS:
            _CONC_FREE -= 1
            _CONC_WAITERS.popleft().set()


def _merge_turn_reasoning(segs: "list[tuple[int, str]]") -> "dict | None":
    """One reasoning item for the WHOLE codex turn. The shim's tool
    loop consumes intermediate upstream responses — and the tool-call
    iterations are where the actual thinking happens — so surfacing
    only the final iteration's reasoning missed the bulk of it
    (Oracle boarding day, 2026-08-24). Segments carry their iteration
    number when there is more than one."""
    if not segs:
        return None
    if len(segs) == 1:
        text = segs[0][1]
    else:
        text = "\n\n".join(f"[iter {i}] {t}" for i, t in segs)
    return {"type": "reasoning", "id": "rs_" + uuid.uuid4().hex,
            "summary": [{"type": "summary_text", "text": text}]}


def _conc_note_concurrency_429() -> None:
    """The upstream's 429 body named CONCURRENCY as the fired limit —
    the one signal that means OUR cap is too high (window/capacity
    429s are somebody else's weather and never reach here).
    Multiplicative decrease; the debt convention (`_CONC_FREE` may go
    negative) lets in-flight calls finish instead of being torn down."""
    if not _CONC_AUTO:
        return
    with _CONC_LOCK:
        global _CONC_CAP, _CONC_FREE, _CONC_LAST_SHRINK
        _CONC_LAST_SHRINK = time.time()
        new = max(_CONC_FLOOR, _CONC_CAP // 2)
        if new < _CONC_CAP:
            delta = _CONC_CAP - new
            _CONC_CAP = new
            _CONC_FREE -= delta
            _log(f"[shim]   gate −{delta} → {_CONC_CAP} "
                  f"(upstream concurrency 429)")


def _touch_heartbeat(attempt_dir: "str | None") -> None:
    """Progress signal for the watchdog's third clock — also written
    while WAITING in the concurrency queue, because an orderly wait on
    a busy account is liveness, not a wedge."""
    if not attempt_dir:
        return
    try:
        with open(os.path.join(attempt_dir, "_shim_heartbeat"), "w"):
            pass
    except OSError:
        pass


#: Total seconds ONE call may spend waiting out 429s (both tiers
#: throttled) before the failure propagates. A throttle is a rolling
#: window — waiting is guaranteed to clear it, and a dead strategist
#: wake costs far more than a minute of patience (user call,
#: 2026-08-22). Bounded so the daemon's own fuses (silent-kill 2400s,
#: seat caps) stay the outer layers, and 0 restores fail-fast.
_429_WAIT_BUDGET = int(os.environ.get("ASTERISM_ZEN_429_BUDGET") or 600)

_UPSTREAM_PLAN = (ZEN, ZEN, ZEN, ZEN_RESCUE, ZEN, ZEN, ZEN, ZEN_RESCUE,
                  ZEN, ZEN)


def _zen_call(body: dict, attempt_dir: "str | None" = None) -> dict:
    """Streaming POST walking `_UPSTREAM_PLAN`: transient failures
    (5xx / transport / empty stream / EITHER tier's 429) step to the
    next slot; non-429 4xx is deterministic — dump and raise.

    An exhausted plan that saw a 429 is a WINDOW, not a failure: both
    tiers throttled means the rolling quota will clear, so the call
    waits (honoring Retry-After when the edge sends one) and walks the
    plan again, up to `_429_WAIT_BUDGET` seconds of waiting — then the
    failure propagates and the daemon's retry machinery decides."""
    wait_spent = 0.0
    while True:
        last: Exception | None = None
        saw_429 = False
        retry_after: int | None = None
        for i, base in enumerate(_UPSTREAM_PLAN):
            try:
                if base != ZEN_RESCUE:
                    _pace()
                    if _conc_enabled():
                        _conc_acquire(attempt_dir)
                        try:
                            return _stream_once(base, body)
                        finally:
                            _conc_release()
                return _stream_once(base, body)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    hdrs = getattr(e, "headers", None) or {}
                    ra = (hdrs.get("Retry-After") or "").strip()
                    if ra.isdigit():
                        retry_after = int(ra)
                    body_head = b""
                    try:
                        body_head = e.read()[:120]
                    except Exception:  # noqa: BLE001
                        pass
                    last = e
                    saw_429 = True
                    if base != ZEN_RESCUE and b"concurrent" in body_head.lower():
                        _conc_note_concurrency_429()
                    # The body names WHICH limit fired (concurrency vs
                    # rpm vs tokens) — evidence the 2026-08-22 storm
                    # took a friend-machine probe to recover.
                    _log(f"[shim]   "
                          f"{('rescue' if base == ZEN_RESCUE else 'primary')}"
                          f" 429 — next slot "
                          f"({body_head.decode('utf-8', 'replace')})")
                elif e.code < 500:
                    raise _dump_4xx(e, body)
                else:
                    e.read()
                    last = e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
            if i == len(_UPSTREAM_PLAN) - 1:
                break
            wait = min(5 * (i + 1), 20)
            _log(f"[shim]   retry {i+1}/{len(_UPSTREAM_PLAN)-1} in {wait}s "
                  f"({last})")
            time.sleep(wait)
        if saw_429 and wait_spent < _429_WAIT_BUDGET:
            wait = float(min(max(retry_after or 0, 30), 120))
            wait_spent += wait
            _log(f"[shim]   throttled through the whole plan — waiting "
                  f"{wait:.0f}s for the window "
                  f"({wait_spent:.0f}s/{_429_WAIT_BUDGET}s of 429 budget)")
            time.sleep(wait)
            continue
        raise last if isinstance(last, Exception) else RuntimeError("no upstream")


def _client_alive(conn) -> bool:
    """Is the codex on the other end of this request still there?

    A killed spawn's shim loop used to keep iterating against the
    upstream — burning the very quota the live spawns were being
    throttled out of — until its final answer died on the dead socket
    (429 storm, 2026-08-22). An HTTP/1.1 client awaiting its response
    sends nothing, so a readable socket here means EOF or RST."""
    try:
        r, _, _ = select.select([conn], [], [], 0)
        if not r:
            return True
        return conn.recv(1, socket.MSG_PEEK) != b""
    except OSError:
        return False


class Shim(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _sse(self, event: str, data: dict) -> None:
        blob = (f"event: {event}\n"
                f"data: {json.dumps(data, ensure_ascii=False)}\n\n").encode()
        self.wfile.write(b"%x\r\n" % len(blob) + blob + b"\r\n")

    def do_POST(self):  # noqa: N802  (stdlib naming)
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n))
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return
        if not body.get("model"):
            if body.get("probe") == "tools":
                # Tool-plane liveness: a REAL tool through _run_tool +
                # request context. The HTTP door kept answering through
                # the whole 2026-08-23 stall while the tool plane sat
                # starved — this probe measures the plane that matters,
                # and ships the snapshot that finds an individual leak.
                pong = _run_tool("ping", {}, None)
                stats = _tools_snapshot()
                stats["probe"] = pong
                blob = json.dumps(stats).encode()
                self.send_response(200 if pong == "pong" else 500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)
                return
            # Liveness curls POST `{}` — answer locally instead of
            # forwarding a model-less request upstream (each one burned
            # an OpenRouter daily-cap slot and manufactured the
            # `invalid_prompt` mystery 400s of 2026-08-22 — which were
            # our own probes all along).
            blob = b'{"error":"no model \xe2\x80\x94 shim alive"}'
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)
            return
        # --- request surgery -----------------------------------------
        if isinstance(body.get("tools"), list):
            flat = []
            for t in body["tools"]:
                ttype = t.get("type")
                if ttype == "namespace":
                    ns = t.get("name") or "ns"
                    for sub in t.get("tools") or []:
                        f = dict(sub)
                        f["name"] = f"{ns}__{sub.get('name')}"
                        flat.append(f)
                elif ttype == "function":
                    flat.append(t)
                # anything else (web_search etc.) dropped: Zen 1210s
            body["tools"] = flat
        declared_tools = {str(t.get("name")) for t in body.get("tools") or []
                          if t.get("type") == "function"}
        body.pop("client_metadata", None)
        body.pop("stream", None)
        nonce = uuid.uuid4().hex[:12]
        inst = body.get("instructions") or ""
        body["instructions"] = f"[session {nonce}]\n{inst}"
        # model naming is per-upstream — _stream_once maps at call time
        # Pin the reasoning phase: unbounded (or effort-high), ox-alpha
        # thinks its whole budget away on long-form outputs and never
        # writes content. OpenRouter's /responses rejects
        # `reasoning.max_tokens` but honors `effort`, and low/medium
        # both cure the runaway (measured 2026-08-22: 1000-word essay
        # delivered at both; unbounded = 8000 tokens of reasoning and
        # zero content).
        body["reasoning"] = {"effort": ZEN_EFFORT}
        # Deterministic channel first: the per-spawn config points codex
        # at `/a/<relpath>/v1` (see _attempt_dir_from_path). The
        # request-text regex stays as fallback (operator overrides
        # that bypass the per-spawn config).
        attempt_dir, turn_budget = _channel_of_path(self.path)
        if attempt_dir is None:
            attempt_dir = _attempt_dir_of(body)
        if not isinstance(body.get("input"), list):
            body["input"] = [body.get("input")] if body.get("input") else []

        # --- Zen loop: absorb flat-MCP calls in the shim -------------
        t0 = time.time()
        iters = 0
        tool_calls_run = 0
        budget_final = False
        lookup_streak = 0
        crawl_nudged = False
        turn_reasoning: "list[tuple[int, str]]" = []
        resp: dict = {}
        try:
            while True:
                if not _client_alive(self.connection):
                    _log(f"[shim] client gone at iter {iters} — "
                          f"abandoning the loop (no quota for orphans)")
                    return
                t_call = time.time()
                resp = _zen_call(body, attempt_dir)
                items = resp.get("output") or []
                if not items:
                    # Degenerate empty response (no output array at
                    # all) — the runaway/overload face that survives
                    # even the effort pin, intermittently. Same cure
                    # as 5xx: retry in place with a fresh nonce so the
                    # poisonable prefix cannot replay it.
                    for extra in range(2):
                        body["instructions"] = (
                            f"[session {uuid.uuid4().hex[:12]}]" + chr(10) + inst)
                        _log(f"[shim]   empty response — retry "
                              f"{extra+1}/2")
                        resp = _zen_call(body, attempt_dir)
                        items = resp.get("output") or []
                        if items:
                            break
                # Harvest EVERY iteration's thinking — the loop consumes
                # intermediate responses, and those are where the model
                # actually reasons; only the final response reaches
                # codex, so this list is what makes the turn's thinking
                # whole (`_merge_turn_reasoning` at synthesis).
                for it in items:
                    if it.get("type") == "reasoning":
                        for s in it.get("summary") or []:
                            if s.get("text"):
                                turn_reasoning.append((iters, s["text"]))
                mine = [it for it in items
                        if it.get("type") == "function_call"
                        and (str(it.get("name", "")).startswith(NS + "__")
                             or str(it.get("name", "")).startswith(
                                 LSP_NS + "__"))]
                _log(f"[shim] iter {iters}: zen {time.time()-t_call:.0f}s, "
                     f"{len(items)} item(s), "
                     + (", ".join(str(it.get('name')).rsplit("__", 1)[-1]
                                  for it in mine) or "final"))
                # Progress heartbeat: codex reports at ITEM granularity,
                # so a long shim loop is total silence on the daemon's
                # clocks — five strategists mid-work were silent-killed
                # at 2400s (2026-08-22; the pacer had stretched legal
                # request spans past the pre-pacer calibration). The
                # watchdog reads this file's mtime as a third clock.
                _touch_heartbeat(attempt_dir)
                if not mine:
                    break
                over_time = (turn_budget is not None
                             and time.time() - t0 > turn_budget)
                if iters >= MAX_TOOL_ITERATIONS or over_time:
                    # The budget guillotine used to be SILENT: 25
                    # measured cap-hits (2026-08-22) cut agents mid
                    # validate→fix loop and committed whatever broken
                    # state was on disk — misread for a whole shift as
                    # "the model submits unverified proofs". At the cap
                    # the pending calls are answered with a refusal
                    # that names the state, and the model gets ONE
                    # wrap-up turn; if it keeps calling tools, cut.
                    if budget_final:
                        break
                    budget_final = True
                    iters += 1
                    for it in items:
                        body["input"].append(it)
                    for it in mine:
                        body["input"].append({
                            "type": "function_call_output",
                            "call_id": it.get("call_id"),
                            "output": (
                                (f"turn TIME budget exhausted "
                                 f"({turn_budget}s — the seat's wall "
                                 f"is close)"
                                 if over_time else
                                 f"tool budget exhausted "
                                 f"({MAX_TOOL_ITERATIONS} iterations)")
                                + ": this call was NOT executed and no "
                                "further calls will run. Reply now "
                                "with your final status — what is "
                                "finished, what is not — and end the "
                                "turn."),
                        })
                    continue
                iters += 1
                # Lookup-crawl detection: formalizers verified lemma
                # names ONE loogle per iteration for 60-90 iterations
                # while patch.lean sat untouched at the seed's `sorry`
                # (both fleets, 2026-08-22). One nudge per request:
                # writing first is the faster name-check.
                names = {str(it.get("name", "")).rsplit("__", 1)[-1]
                         for it in mine}
                if names <= {"loogle", "inspect", "paper_search"}:
                    lookup_streak += 1
                else:
                    lookup_streak = 0
                if lookup_streak == 12 and not crawl_nudged:
                    crawl_nudged = True
                    body["input"].append({
                        "type": "message", "role": "user",
                        "content": [{"type": "input_text", "text": (
                            "[framework] 12 consecutive lookup-only "
                            "iterations and the working file is "
                            "untouched. Stop enumerating names: write "
                            "the draft NOW with your best guesses — "
                            "validate_file names every unknown "
                            "identifier precisely in one shot, a "
                            "faster name-check than loogle "
                            "one-by-one. (loogle also takes several "
                            "patterns in one call, one per line.)")}],
                    })
                if iters == MAX_TOOL_ITERATIONS - 10:
                    # Approach warning, so convergence is a choice the
                    # model gets to make before the refusals start.
                    body["input"].append({
                        "type": "message", "role": "user",
                        "content": [{"type": "input_text", "text": (
                            "[framework] tool budget: ~10 iterations "
                            "remain. Converge now — bring your working "
                            "file to its best verified state and "
                            "finish; do not start new explorations.")}],
                    })
                for it in items:
                    body["input"].append(it)
                    if it not in mine:
                        continue
                    full = str(it.get("name"))
                    try:
                        args = json.loads(it.get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    t_tool = time.time()
                    if full not in declared_tools:
                        # The whitelist is the request's OWN declared
                        # list (which the seat-scoped MCP server
                        # produced) — the model naming an undeclared
                        # tool is a capability probe, not a route
                        # (owner ruling 2026-08-22: seats get exactly
                        # their surface, on every provider).
                        tool = full[full.rfind("__") + 2:] or full
                        out = (f"{full} is not in this seat's toolset. "
                               f"Available: "
                               + ", ".join(sorted(declared_tools)))
                    elif full.startswith(LSP_NS + "__"):
                        tool = full[len(LSP_NS) + 2:]
                        out = _run_lsp_tool(tool, args, attempt_dir)
                    else:
                        tool = full[len(NS) + 2:]
                        out = _run_tool(tool, args, attempt_dir)
                    # Name the target and echo the result HEAD: a 99B
                    # success and a 99B refusal were indistinguishable
                    # by size, which cost a whole forensics round on
                    # "where did decision.json go" (g636, 2026-08-22).
                    arg_hint = str(args.get("path") or args.get("query")
                                   or args.get("target")
                                   or args.get("pattern") or "")[:60]
                    _log(f"[shim]   tool {tool}({arg_hint}) "
                          f"{time.time()-t_tool:.1f}s "
                          f"-> {len(out)}B: {out[:70]!r}")
                    tool_calls_run += 1
                    body["input"].append({
                        "type": "function_call_output",
                        "call_id": it.get("call_id") or it.get("id"),
                        "output": out})
        except urllib.error.HTTPError as e:
            payload = e.read()
            _log(f"[shim] upstream {e.code} after {time.time()-t0:.0f}s "
                  f"(iters={iters}): {payload[:160]!r}")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        except Exception as e:  # noqa: BLE001 — network layer
            _log(f"[shim] transport error (iters={iters}): {e}")
            self.send_response(502)
            self.end_headers()
            return

        # --- synthesize a conformant Responses SSE stream ------------
        # The final response's own reasoning item is dropped here — its
        # text is already in turn_reasoning, and the merged item below
        # carries the whole turn (every iteration), not just the tail.
        items = [it for it in (resp.get("output") or [])
                 if it.get("type") != "reasoning"
                 and not (it.get("type") == "function_call"
                          and (str(it.get("name", "")).startswith(NS + "__")
                               or str(it.get("name", "")).startswith(
                                   LSP_NS + "__")))]
        merged_rsn = _merge_turn_reasoning(turn_reasoning)
        if merged_rsn is not None:
            items.insert(0, merged_rsn)
        usage = resp.get("usage") or {}
        _log(f"[shim] ok {time.time()-t0:.0f}s iters={iters} "
              f"tools={tool_calls_run} items={len(items)} "
              f"usage={usage.get('output_tokens')}out")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        seq = 0

        def ev(event: str, extra: dict) -> None:
            nonlocal seq
            seq += 1
            self._sse(event, {"type": event, "sequence_number": seq, **extra})

        shell = {k: v for k, v in resp.items() if k != "output"}
        shell["output"] = []
        ev("response.created", {"response": shell})
        ev("response.in_progress", {"response": shell})
        for idx, item in enumerate(items):
            ev("response.output_item.added",
               {"output_index": idx, "item": {**item,
                **({"content": []} if item.get("type") == "message" else {})}})
            if item.get("type") == "message":
                for ci, part in enumerate(item.get("content") or []):
                    ev("response.content_part.added",
                       {"item_id": item.get("id"), "output_index": idx,
                        "content_index": ci, "part": {**part, "text": ""}})
                    text = part.get("text") or ""
                    if text:
                        ev("response.output_text.delta",
                           {"item_id": item.get("id"), "output_index": idx,
                            "content_index": ci, "delta": text,
                            "logprobs": []})
                    ev("response.output_text.done",
                       {"item_id": item.get("id"), "output_index": idx,
                        "content_index": ci, "text": text, "logprobs": []})
                    ev("response.content_part.done",
                       {"item_id": item.get("id"), "output_index": idx,
                        "content_index": ci, "part": part})
            elif item.get("type") == "function_call":
                args = item.get("arguments") or ""
                if args:
                    ev("response.function_call_arguments.delta",
                       {"item_id": item.get("id"), "output_index": idx,
                        "delta": args})
                ev("response.function_call_arguments.done",
                   {"item_id": item.get("id"), "output_index": idx,
                    "arguments": args})
            ev("response.output_item.done",
               {"output_index": idx, "item": item})
        done = dict(resp)
        done["status"] = "completed"
        done["output"] = items
        ev("response.completed", {"response": done})
        self.wfile.write(b"0\r\n\r\n")

    def log_message(self, *a):  # noqa: D102 — quiet
        pass


#: Service files for the detached form (`start`/`stop`/`status`). The
#: shim used to live as a child of whichever operator session launched
#: it — session dies (or the session's task registry sweeps), fleet
#: goes dark (2026-08-22: three in-session relaunches were externally
#: stopped and the daemon fed a dead channel for 40 minutes). Detached,
#: it belongs to nobody's session.
_PID_FILE = os.path.join(_REPO, ".asterism", "zen_shim.pid")
_SVC_LOG = os.path.join(_REPO, ".asterism", "logs", "zen_shim.log")

# Windows' `signal` module has no `SIGKILL` attribute — there is no OS
# equivalent, so CPython omits it on that build. The POSIX kill path
# below is dead code in production on Windows (gated on `os.name`), but
# this repo's test suite runs ON Windows and forces the branch via
# monkeypatch to cover it, so the POSIX signal number (always 9) is
# pinned here rather than referenced as `signal.SIGKILL` directly.
_SIGKILL = getattr(signal, "SIGKILL", 9)


def _proc_cmdline_mentions(pid: int, needle: str) -> bool:
    """Best-effort pid-reuse guard for POSIX liveness: True when
    `/proc/<pid>/cmdline` can't be read at all (not Linux, permission
    denied, sandboxed) — an unreadable cmdline is "can't tell", and a
    liveness probe must not false-negative a shim that IS alive just
    because it can't double-check identity. False only when the file
    was readable and genuinely does not mention `needle`."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read()
    except OSError:
        return True
    return needle.encode() in cmdline


def _pid_alive_posix(pid: int) -> bool:
    """`os.kill(pid, 0)`: ESRCH (ProcessLookupError) means dead, EPERM
    (PermissionError) means alive but owned by someone else — still a
    live pid, which is all liveness means. Followed by a best-effort
    identity check so a pid recycled by an unrelated process between
    our pid-file write and this read is not reported as "the shim is
    still running"."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return _proc_cmdline_mentions(pid, "zen_shim")


def _kill_pid_posix(pid: int, grace_sec: float = 3.0) -> None:
    """SIGTERM, bounded grace wait, then SIGKILL — the POSIX half of
    `_svc_stop`. Best-effort throughout: the caller only reaches here
    after `_pid_alive` already confirmed this pid IS the shim, but the
    process can still exit on its own between that check and this
    signal, and `os.kill` must not raise into a `stop` command."""
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        return
    deadline = time.monotonic() + grace_sec
    while time.monotonic() < deadline:
        if not _pid_alive_posix(pid):
            return
        time.sleep(0.1)
    try:
        os.kill(pid, _SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _pid_alive(pid: int) -> bool:
    """tasklist, not kill-0: Git-Bash-style probes cannot see native
    Windows processes (operator rule 8). POSIX uses the real kill-0
    probe instead (`_pid_alive_posix`) — Windows has no signal 0."""
    if os.name != "nt":
        return _pid_alive_posix(pid)
    import subprocess
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10).stdout
        return f'"{pid}"' in out
    except Exception:  # noqa: BLE001 — a probe must never raise
        return False


def _svc_status(port: int) -> "tuple[int | None, bool]":
    """(pid from the pid file if that process is alive, port answers)."""
    pid = None
    try:
        cand = int(open(_PID_FILE, encoding="ascii").read().strip())
        if _pid_alive(cand):
            pid = cand
    except (OSError, ValueError):
        pass
    try:
        import urllib.request as _rq
        req = _rq.Request(f"http://127.0.0.1:{port}/v1", method="GET")
        try:
            _rq.urlopen(req, timeout=3)
            answering = True
        except urllib.error.HTTPError:
            answering = True
    except Exception:  # noqa: BLE001
        answering = False
    return pid, answering


def _detach_popen_kwargs() -> dict:
    """Platform-specific `subprocess.Popen` kwargs so the shim child
    survives the launching session. Windows: no session concept — flags
    that detach it from the console and its own process group.
    POSIX: `start_new_session=True` (`setsid`) — without it the child
    inherits the launching shell's session and dies with a SIGHUP when
    that shell/terminal exits, exactly the "shim died with the
    operator's session" failure this detached form exists to avoid
    (2026-08-22, see the comment above `_PID_FILE`)."""
    import subprocess
    if os.name == "nt":
        return {"creationflags":
                (getattr(subprocess, "DETACHED_PROCESS", 0)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))}
    return {"start_new_session": True}


def _svc_start(port: int) -> int:
    import subprocess
    pid, answering = _svc_status(port)
    if answering:
        print(f"already serving on {port}"
              + (f" (pid {pid})" if pid else " (pid unknown)"))
        return 0
    # Fail LOUD before detaching: the child runs THIS interpreter, and
    # a venv python without the tool deps detached fine and then
    # answered every tool call "No module named 'mcp'" (2026-08-23).
    try:
        _tools_module()
    except Exception as e:  # noqa: BLE001 — refuse to detach broken
        print(f"refusing to detach: this interpreter ({sys.executable}) "
              f"cannot import the tool surface ({e}). Start the shim "
              f"with the framework's Python.")
        return 1
    os.makedirs(os.path.dirname(_SVC_LOG), exist_ok=True)
    log = open(_SVC_LOG, "ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "Tooling.llm.zen_shim", str(port)],
        cwd=_REPO, stdout=log, stderr=log,
        stdin=subprocess.DEVNULL, close_fds=True,
        **_detach_popen_kwargs())
    with open(_PID_FILE, "w", encoding="ascii") as fh:
        fh.write(str(proc.pid))
    for _ in range(20):
        time.sleep(0.5)
        if _svc_status(port)[1]:
            print(f"zen shim detached: pid {proc.pid}, port {port}, "
                  f"log {_SVC_LOG}")
            return 0
    print(f"started pid {proc.pid} but port {port} is not answering — "
          f"see {_SVC_LOG}")
    return 1


def _svc_stop(port: int) -> int:
    pid, answering = _svc_status(port)
    if pid is None:
        print("no live pid on record"
              + (" (but the port answers — a foreign shim?)"
                 if answering else "; nothing to stop"))
        # A stale pid file (dead pid, or one recycled by an unrelated
        # process — `_svc_status` only returns a pid that passed
        # `_pid_alive`'s identity check) must not linger: the next
        # `start` would read it and report the wrong pid forever.
        try:
            os.remove(_PID_FILE)
        except OSError:
            pass
        return 0 if not answering else 1
    if os.name == "nt":
        import subprocess
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True)
    else:
        _kill_pid_posix(pid)
    try:
        os.remove(_PID_FILE)
    except OSError:
        pass
    print(f"stopped pid {pid}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    cmd = argv[0] if argv and not argv[0].isdigit() else None
    port = int(next((a for a in argv if a.isdigit()), 8898))
    if cmd == "start":
        return _svc_start(port)
    if cmd == "stop":
        return _svc_stop(port)
    if cmd == "status":
        pid, answering = _svc_status(port)
        print(f"pid={pid or '-'} port={port} "
              f"{'answering' if answering else 'DEAD'}")
        if answering:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/v1/responses",
                    data=b'{"probe": "tools"}',
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    st = json.loads(r.read())
                print(f"tool plane: probe={st.get('probe')} "
                      f"running={len(st.get('tools_running') or [])} "
                      f"oldest={st.get('oldest_tool_age_sec')}s "
                      f"upstream={st.get('upstream_slots')}")
                for t in (st.get("tools_running") or [])[:5]:
                    print(f"  {t['age_sec']:>7.1f}s  {t['tool']}"
                          f"  {t['scope']}")
            except Exception as e:  # noqa: BLE001 — status is best-effort
                print(f"tool plane: probe failed ({e}) — old shim build "
                      f"or wedged tool plane")
        return 0 if answering else 1
    if cmd is not None:
        print(f"unknown command {cmd!r} — use start|stop|status|<port>")
        return 2
    _key_for(ZEN)  # fail fast on a missing primary key
    try:
        _key_for(ZEN_RESCUE)
    except SystemExit:
        _log("[shim] WARNING: no rescue-tier key — running primary-only")
    _log(f"[shim] zen shim v6 on 127.0.0.1:{port} -> {ZEN} "
          f"(rescue: {ZEN_RESCUE})")
    class _ExclusiveServer(http.server.ThreadingHTTPServer):
        # SO_REUSEADDR on Windows lets a second shim BIND THE SAME
        # PORT and silently split the traffic — observed live
        # 2026-08-22 (two listeners, two pacers, the rolling-window
        # budget doubled). A port singleton must refuse, loudly.
        # On POSIX the same flag admits NO second live listener — it
        # only lets a restart rebind over a dead process's TIME_WAIT
        # remnants, without which a systemd restart strikes out on
        # its StartLimit before the ~60s remnant clears (Oracle
        # boarding, 2026-08-24). Exclusive where exclusivity is
        # real, reusable where it is safe.
        allow_reuse_address = (os.name != "nt")

    _ExclusiveServer(("127.0.0.1", port), Shim).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
