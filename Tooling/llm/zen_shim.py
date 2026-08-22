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
functions; the per-spawn context they need travels in env
(`ASTERISM_SPAWN_ATTEMPT_DIR`), which the shim recovers by parsing the
attempts-dir path out of the request text and pins under a global lock
for the duration of each call.

Run:  python -m Tooling.llm.zen_shim [port]   (default 8898)
Key:  OPENCODE_ZEN_API_KEY env, or .env's OPENCODE_ZEN_API_KEY.
"""
from __future__ import annotations

import http.server
import io
import json
import os
import re
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
MAX_TOOL_ITERATIONS = 80

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

def _log(msg: str) -> None:
    """Shim logs go to STDERR: the tool wrappers in mcp_tools capture
    sys.stdout process-wide (contextlib.redirect_stdout), and in this
    THREADED server one request's capture was swallowing every other
    thread's shim prints — the model received paper_search results
    that BEGAN with '[shim] iter 31: ...' (live, 2026-08-22)."""
    print(msg, file=sys.stderr)


_TOOL_LOCK = threading.Lock()
# Both separators: codex 0.147 rendered the skills-preamble paths with
# backslashes, 0.149 renders them with FORWARD slashes — the
# backslash-only pattern silently stopped matching after the upgrade,
# attempt_dir came back None, every write_file was refused, and the
# strategist declared its batch committed anyway (g629, 2026-08-22).
_ATTEMPT_RE = re.compile(
    r"[A-Za-z]:[\\/][^\s'\"]*\.attempts[\\/][0-9a-fA-F-]{36}")


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


def _run_tool(name: str, args: dict, attempt_dir: "str | None") -> str:
    mod = _tools_module()
    fn = getattr(mod, name, None)
    if fn is None:
        return f"unknown tool {name!r}"
    with _TOOL_LOCK:
        prior = os.environ.get("ASTERISM_SPAWN_ATTEMPT_DIR")
        try:
            if attempt_dir:
                os.environ["ASTERISM_SPAWN_ATTEMPT_DIR"] = attempt_dir
            try:
                return str(fn(**args))
            except TypeError as e:
                return f"bad arguments for {name}: {e}"
            except Exception as e:  # noqa: BLE001 — tool result surface
                return f"{name} raised {type(e).__name__}: {e}"
        finally:
            if prior is None:
                os.environ.pop("ASTERISM_SPAWN_ATTEMPT_DIR", None)
            else:
                os.environ["ASTERISM_SPAWN_ATTEMPT_DIR"] = prior


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
    (written by pipeline._write_mcp_config)."""
    cached = _LSP_SESSIONS.get(attempt_dir)
    if cached:
        return cached
    try:
        token = open(os.path.join(attempt_dir, "_gateway_session.token"),
                     encoding="utf-8").read().strip()
    except OSError:
        return None
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
    if not attempt_dir:
        return "lsp tools need a session; no attempts dir found in request"
    sess = _lsp_session_for(attempt_dir)
    if sess is None:
        return "no _gateway_session.token in attempts dir — lsp unavailable"
    sid, token = sess
    hdr = {"X-Asterism-Session": token}
    if sid:
        hdr["Mcp-Session-Id"] = sid
    try:
        obj, _ = _mcp_http({"jsonrpc": "2.0", "id": 2,
                            "method": "tools/call",
                            "params": {"name": name, "arguments": args}},
                           hdr)
    except urllib.error.HTTPError as e:
        return f"lsp gateway HTTP {e.code}: {e.read()[:200]!r}"
    except Exception as e:  # noqa: BLE001 — tool result surface
        return f"lsp transport error: {e}"
    if not obj:
        return "lsp gateway returned no parseable response"
    if obj.get("error"):
        return f"lsp error: {obj['error']}"
    result = obj.get("result") or {}
    parts = result.get("content") or []
    text = "".join(p.get("text", "") for p in parts
                   if isinstance(p, dict))
    return text or json.dumps(result)[:2000]


def _attempt_dir_of(body: dict) -> "str | None":
    # Scan the WHOLE request: the 20K slice used here first let the
    # skills preamble push the environment context (which carries the
    # attempts dir) past the window — attempt_dir=None, every
    # write_file refused, agent_no_output (measured 2026-08-22).
    hay = json.dumps(body.get("instructions", "")) + json.dumps(
        body.get("input", ""))
    m = _ATTEMPT_RE.search(hay.replace("\\\\", "\\"))
    return m.group(0) if m else None


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
    return {"id": "resp_" + uuid.uuid4().hex,
            "object": "response",
            "created_at": int(time.time()),
            "model": chat["model"],
            "status": "completed",
            "output": items,
            "usage": {"input_tokens": in_t, "output_tokens": out_t,
                      "total_tokens": usage.get("total_tokens")
                      or (in_t + out_t)}}


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
_UPSTREAM_PLAN = (ZEN, ZEN, ZEN, ZEN_RESCUE, ZEN, ZEN, ZEN, ZEN_RESCUE,
                  ZEN, ZEN)


def _zen_call(body: dict) -> dict:
    """Streaming POST walking `_UPSTREAM_PLAN`: transient failures
    (5xx / transport / empty stream / EITHER tier's 429) step to the
    next slot; non-429 4xx is deterministic — dump and raise. The last
    slot's failure propagates."""
    last: Exception | None = None
    for i, base in enumerate(_UPSTREAM_PLAN):
        is_last = i == len(_UPSTREAM_PLAN) - 1
        try:
            return _stream_once(base, body)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                e.read()
                last = e
                _log(f"[shim]   {('rescue' if base == ZEN_RESCUE else 'primary')}"
                      f" 429 — next slot")
            elif e.code < 500:
                raise _dump_4xx(e, body)
            else:
                e.read()
                last = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
        if is_last:
            break
        wait = min(5 * (i + 1), 20)
        _log(f"[shim]   retry {i+1}/{len(_UPSTREAM_PLAN)-1} in {wait}s "
              f"({last})")
        time.sleep(wait)
    raise last if isinstance(last, Exception) else RuntimeError("no upstream")


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
        # at `/a/<uuid>/v1`, so the URL names the attempts dir outright.
        # The request-text regex stays as fallback (operator overrides
        # that bypass the per-spawn config).
        m_aid = re.search(r"/a/([0-9a-fA-F-]{36})/", self.path or "")
        attempt_dir = (os.path.join(_REPO, ".attempts", m_aid.group(1))
                       if m_aid else _attempt_dir_of(body))
        if not isinstance(body.get("input"), list):
            body["input"] = [body.get("input")] if body.get("input") else []

        # --- Zen loop: absorb flat-MCP calls in the shim -------------
        t0 = time.time()
        iters = 0
        tool_calls_run = 0
        resp: dict = {}
        try:
            while True:
                t_call = time.time()
                resp = _zen_call(body)
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
                        resp = _zen_call(body)
                        items = resp.get("output") or []
                        if items:
                            break
                mine = [it for it in items
                        if it.get("type") == "function_call"
                        and (str(it.get("name", "")).startswith(NS + "__")
                             or str(it.get("name", "")).startswith(
                                 LSP_NS + "__"))]
                _log(f"[shim] iter {iters}: zen {time.time()-t_call:.0f}s, "
                     f"{len(items)} item(s), "
                     + (", ".join(str(it.get('name'))[len(NS)+2:]
                                  for it in mine) or "final"))
                if not mine or iters >= MAX_TOOL_ITERATIONS:
                    break
                iters += 1
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
        items = [it for it in (resp.get("output") or [])
                 if not (it.get("type") == "function_call"
                         and (str(it.get("name", "")).startswith(NS + "__")
                              or str(it.get("name", "")).startswith(
                                  LSP_NS + "__")))]
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


def main() -> int:
    _key_for(ZEN)  # fail fast on a missing primary key
    try:
        _key_for(ZEN_RESCUE)
    except SystemExit:
        _log("[shim] WARNING: no rescue-tier key — running primary-only")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8898
    _log(f"[shim] zen shim v6 on 127.0.0.1:{port} -> {ZEN} "
          f"(rescue: {ZEN_RESCUE})")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Shim).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
