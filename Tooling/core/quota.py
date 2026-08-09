"""Who cannot spawn right now, per (provider, model) — the quota ledger.

The framework used to hold one boolean: "quota is exhausted". Reality
has never been that shape, and 2026-08-06 is what it costs. The claude
usage endpoint returns a `limits[]` array in which a per-model weekly
cap sat at 100% for `Fable` while the shared five-hour window was at 1%
and the weekly total at 58%. `exhausted_until` folded all of it into
`True`, the dispatcher paused EVERYTHING, and eleven finished proposals
were thrown away — by a run whose formalizer was on Gemini and whose
judge could have moved to Opus, neither of which had any quota problem
at all.

So the ledger answers a question with two arguments, not zero:

    blocked(provider, model) -> Block | None

A `Block` with `model=None` covers every model on that provider (the
shared five-hour window); a Block naming a model covers just that one
(the scoped weekly cap).

Providers answer in their own dialect and are asked through one
interface. WHETHER a provider is asked at all is not a property of its
name but of its declaration (`llm/capabilities.py`): `usage_endpoint`
decides, and `register_declared_probes` wires every declared provider
accordingly. A backend that cannot answer — agy has no usage API at all
— gets the honest empty case, and so does one nobody has measured yet.

Pipelines are NOT independent, which is the other half of the lesson.
A Strategist proposal that no judge can review is a proposal that gets
discarded; a pre-search whose work turn cannot run is a search paid for
and thrown away. `BOUND` records those couplings, and a bound group is
runnable only when every member is.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

#: Pipelines that live or die together. If any member's model is
#: blocked, none of them may be dispatched — running the others only
#: manufactures work that the missing member was going to consume.
#:
#:   strategist + adversary: the author and the judge of the same
#:     artifact. A proposal with no judge is not "partial progress", it
#:     is 25-28k output tokens that get discarded (11 of them, 2026-08-06).
#:   presearch + formalizer: pre-search is a station of the formalizer
#:     chain (`pipeline/_stages.py`), and its whole output is a section
#:     of the work turn's context. Either the chain runs or the search
#:     is waste.
BOUND: "tuple[frozenset[str], ...]" = (
    frozenset({"strategist", "adversary"}),
    frozenset({"presearch", "formalizer"}),
)


#: seat name (the config key, lowercase) -> the queue/dispatch kind that
#: spawns it. Two spellings for one pipeline is exactly how the first
#: wiring of this module failed in production (2026-08-07): the ledger
#: answered in seat names, the dispatcher asked in queue kinds, and the
#: mismatch silently disabled both halves — `observe()` never fired
#: because the seat lookup missed, and the hold wrote a key the refill
#: pass does not read. Seats with no entry are stations inside another
#: pipeline (pre-search) or non-dispatch surfaces; they matter only
#: through `BOUND`.
DISPATCH_KIND: "dict[str, str]" = {
    "strategist": "Strategist",
    "formalizer": "Formalizer",
    "librarian": "Librarian",
    "scholar": "Scholar",
}


@dataclass(frozen=True)
class Block:
    """One spawn surface that is unavailable, and until when.

    `model=None` means every model on this provider. `until=None` means
    the provider told us it is exhausted but not when it recovers —
    callers must not treat that as "forever", only as "not now".
    """

    provider: str
    model: "str | None"
    until: "float | None" = None
    detail: str = ""

    def covers(self, provider: str, model: "str | None") -> bool:
        if provider != self.provider:
            return False
        if self.model is None:
            return True
        if not model:
            return False
        return _same_model(self.model, model)


def _same_model(scoped: str, configured: str) -> bool:
    """Does a provider's scope label name the configured model?

    The claude endpoint labels a scoped cap with a display name
    ('Fable'), while the config carries an id ('claude-fable-5'). Match
    on containment after lowercasing, which is loose on purpose: a false
    NEGATIVE spawns into a dead window and loses a proposal, a false
    positive only makes the framework wait. Where the labels diverge
    beyond this, the provider probe should normalize before returning.
    """
    a, b = scoped.strip().lower(), configured.strip().lower()
    return bool(a) and (a in b or b in a)


#: provider name -> probe. A probe returns the blocks it can see, and
#: raises nothing: an unreachable endpoint is "cannot confirm", which
#: must not read as "blocked" (a broken probe would otherwise halt the
#: framework) nor as "clear" for a provider that never answers.
_PROBES: "dict[str, Callable[[], list[Block]]]" = {}


def register_probe(provider: str, probe: "Callable[[], list[Block]]") -> None:
    _PROBES[provider] = probe


def _claude_blocks() -> "list[Block]":
    """Read the subscription endpoint, keeping the per-model dimension.

    Global windows (five_hour / seven_day) block every model; an active
    `weekly_scoped` limit blocks only the model its scope names.
    """
    from . import usage_quota
    try:
        raw = usage_quota.fetch_usage()
    except Exception:  # noqa: BLE001 — unreachable ≠ exhausted
        return []
    if not raw:
        return []
    out: "list[Block]" = []
    bar = usage_quota.EXHAUSTED_UTILIZATION
    for key in ("five_hour", "seven_day"):
        node = raw.get(key)
        if node and node.get("utilization") is not None:
            if float(node["utilization"]) >= bar:
                out.append(Block(
                    "claude", None,
                    usage_quota._parse_reset(node.get("resets_at")),
                    f"{key} window at {node['utilization']}%"))
    for lim in raw.get("limits") or []:
        if lim.get("kind") != "weekly_scoped" or not lim.get("is_active"):
            continue
        if float(lim.get("percent") or 0.0) < bar:
            continue
        scope = (lim.get("scope") or {}).get("model") or {}
        name = str(scope.get("display_name") or "").strip()
        out.append(Block(
            "claude", name or None,
            usage_quota._parse_reset(lim.get("resets_at")),
            f"weekly cap for {name or 'this plan'} at {lim.get('percent')}%"))
    return out


def _no_endpoint() -> "list[Block]":
    """Providers with no usage API. Their exhaustion is still inferred
    from spawn failures by the dispatcher's breaker — this returns
    nothing rather than pretending to know.

    CONSEQUENCE, recorded so nobody re-litigates it: a provider wired to
    this probe can never receive a POSITIVE quota confirmation. There is
    no `resets_at` for `core/quota_wait` to sleep to, and a spawn that
    dies without one of the provider's own refusal markers is charged as
    an agent failure. That is the correct reading of
    `usage_endpoint=False` — the framework declines to invent a
    confirmation nobody gave it — not agy being treated unfairly. The
    cure is an endpoint, not a heuristic.
    """
    return []


#: Real probes, keyed by canonical provider name. A provider is wired to
#: its probe HERE only if its declaration says it can answer; the
#: registry below reads `usage_endpoint`, not the provider's name.
_ENDPOINT_PROBES: "dict[str, Callable[[], list[Block]]]" = {
    "claude": _claude_blocks,
}


def register_declared_probes() -> None:
    """Wire every declared provider to a probe, chosen by its
    DECLARATION rather than by its name.

    This used to be three literal `register_probe(<name>, …)` lines, two
    of them pointing at `_no_endpoint` — which meant a fourth backend
    (codex is next) got no line at all, and `Ledger.refresh` simply
    never asked it anything. Silent, and indistinguishable from "that
    provider is fine". Now the question is asked of the declaration:
    `usage_endpoint=True` and no probe implemented is a loud gap;
    `usage_endpoint=False` is the honest empty case; an UNDECLARED
    provider lands in the empty case too, because a backend nobody
    measured must not be assumed to have an endpoint.
    """
    from ..llm import capabilities as _caps
    for name, caps in _caps.CAPABILITIES.items():
        if not caps.usage_endpoint:
            register_probe(name, _no_endpoint)
            continue
        probe = _ENDPOINT_PROBES.get(name)
        if probe is None:
            print(f"[quota] provider {name!r} declares a usage endpoint "
                  f"but core/quota.py implements no probe for it — its "
                  f"quota is invisible to the ledger", flush=True)
            register_probe(name, _no_endpoint)
            continue
        register_probe(name, probe)


register_declared_probes()


class Ledger:
    """A snapshot of every provider's blocks, cached for `ttl` seconds.

    Cached because the dispatch loop asks per tick and the endpoint is a
    network call that answers 429 exactly when every client wants it.
    """

    def __init__(self, ttl: float = 60.0,
                 clock: "Callable[[], float]" = time.time) -> None:
        self._ttl = ttl
        self._clock = clock
        self._at = 0.0
        self._blocks: "list[Block]" = []
        self._probed: "list[Block]" = []
        #: Blocks learned from failed spawns (see `observe`) — the only
        #: channel a provider without a usage API has.
        self._observed: "list[Block]" = []

    #: How long an OBSERVED block (a spawn that died on quota) is
    #: trusted when the provider gave no reset time. Long enough that
    #: the bound group stops thrashing, short enough that a misread
    #: costs one wait rather than the rest of the run.
    OBSERVED_TTL_SEC = 900.0

    def observe(self, provider: str, model: "str | None",
                *, until: "float | None" = None, detail: str = "") -> None:
        """Record a block learned from a FAILED SPAWN rather than a
        usage API.

        This is how a provider without a usage endpoint joins the
        ledger. agy has no quota surface (`agy --help`, probed
        2026-08-07: no usage/quota subcommand) but it does classify its
        own refusals — `antigravity_cli._QUOTA_MARKERS` turns them into
        rc=126. Before this, that signal only cooled the one kind that
        happened to spawn; now it lands in the same ledger the probes
        feed, so the BOUND group stops together instead of the sibling
        continuing to manufacture work for a seat that cannot run.
        """
        self._observed.append(Block(
            provider, model,
            until if until is not None
            else self._clock() + self.OBSERVED_TTL_SEC,
            detail or "observed: spawn refused on quota"))

    def refresh(self, *, force: bool = False) -> "list[Block]":
        now = self._clock()
        self._observed = [b for b in self._observed
                          if b.until is None or b.until > now]
        if force or not self._at or now - self._at >= self._ttl:
            found: "list[Block]" = []
            for probe in list(_PROBES.values()):
                try:
                    found.extend(probe())
                except Exception:  # noqa: BLE001 — a probe must not halt us
                    continue
            self._probed = [b for b in found
                            if b.until is None or b.until > now]
            self._at = now
        else:
            self._probed = [b for b in self._probed
                            if b.until is None or b.until > now]
        self._blocks = self._probed + self._observed
        return self._blocks

    def blocked(self, provider: str,
                model: "str | None") -> "Optional[Block]":
        for b in self.refresh():
            if b.covers(provider, model):
                return b
        return None

    def blocked_kinds(
        self, seats: "dict[str, tuple[str, str | None]]",
    ) -> "dict[str, Block]":
        """Which pipeline kinds cannot run, given `kind -> (provider,
        model)`.

        A kind is blocked by its own seat OR by any seat it is bound to
        (`BOUND`) — the binding is what stops the framework from
        producing an artifact whose consumer is missing.
        """
        direct = {kind: blk for kind, (prov, mdl) in seats.items()
                  if (blk := self.blocked(prov, mdl)) is not None}
        out = dict(direct)
        for group in BOUND:
            hit = next((direct[k] for k in group if k in direct), None)
            if hit is None:
                continue
            for k in group:
                out.setdefault(k, hit)
        return out
