// The places of a project on every page of it (Asterism.side): /api/channels on the pages' rhythm (the rail counts
// what is important from it; the messages pages read the places), the members from /api/members (the presence marks,
// the member list, the profile cards), and the second column of chat (#side-channels: the channels, each with a small
// lock when some members may not read it, its settings mark and menu: right click, the context-menu key or Shift+F10: mark as read, mute, copy its address, its
// settings, create a channel) and of private messages (#dm-list: the conversations, newest first, and #dm-new, a
// menu of the members one may write to privately). Every page of the project also tells the server it is open
// (POST /api/presence at once and every few seconds, data-beat on the rail): that is a person's presence.
// The rail and the drawer are rail.js's; the project menu is project.js's.
"use strict";
(function () {
  var A = window.Asterism, rail = document.getElementById("rail"), side = document.getElementById("side");
  if (!A || !rail) return;
  var t = A.t, make = A.make;
  var SLUG = rail.dataset.slug, ME = rail.dataset.me;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var PLACES_EVERY_MS = 4000, MEMBERS_EVERY_MS = 15000;
  var lists = {channels: document.getElementById("side-channels"), "private": document.getElementById("dm-list")};
  var dmNone = document.getElementById("dm-none");

  var S = A.side = {
    places: null,                     // what /api/channels answered last
    directory: A.parseJSON(rail.dataset.directory, {}),   // name -> {kind, online, owner}
    members: null,                    // what /api/members answered last
    current: null,                    // the place open on the messages page
    listeners: [], memberListeners: []
  };
  var PERMS = A.parseJSON(rail.dataset.perms, []);
  A.can = function (perm) { return PERMS.indexOf(perm) >= 0; };
  S.onChange = function (fn) { S.listeners.push(fn); if (S.places) fn(S.places); };
  S.onMembers = function (fn) { S.memberListeners.push(fn); if (S.members) fn(S.members); };
  S.setCurrent = function (place) { S.current = place; draw(true); };

  // ------------------------------------------------------------------ the lists

  // A channel is chat's (/slug#%23name); a private conversation has a page of its own (/slug/dm/name).
  function hrefOf(place) {
    var base = "/" + encodeURIComponent(SLUG);
    return place.charAt(0) === "#" ? base + "#" + encodeURIComponent(place) : base + "/dm/" + encodeURIComponent(place);
  }
  S.hrefOf = hrefOf;

  // Shape says who (a square for a person, a disc for an agent), fill says state (filled while online).
  function presence(who) {
    var mark = make("span", "presence " + (who && who.kind === "agent" ? "agent" : "person") + (who && who.online ? " on" : ""));
    mark.setAttribute("role", "img");
    mark.setAttribute("aria-label", t(who && who.online ? "presence.online" : "presence.offline"));
    return mark;
  }
  S.presence = presence;

  // Important unread: the inverted pill, muted or not (muting silences a place's talk, not a message that names the
  // reader). Other unread: the plain count, none in a muted place.
  function counts(a, unread, important, muted) {
    if (important) {
      var pill = make("span", "pill", String(important));
      pill.setAttribute("aria-hidden", "true");
      a.append(pill, make("span", "vh", muted ? t("nav.important_muted", {k: important})
                                              : t("nav.important", {n: unread, k: important})));
    } else if (unread && !muted) {
      var c = make("span", "count", String(unread));
      c.setAttribute("aria-hidden", "true");
      a.append(c, make("span", "vh", t("nav.unread", {n: unread})));
    }
  }

  function settingsHref(name) {
    return "/" + encodeURIComponent(SLUG) + "/channels/" + encodeURIComponent(name) + "/settings";
  }
  S.settingsHref = settingsHref;

  function item(place, inner, unread, important, muted) {
    var li = make("li", "place-row"), a = make("a", "place" + (unread && !muted ? " unread" : "") + (muted ? " muted" : ""));
    a.href = hrefOf(place);
    a.dataset.place = place;
    a.dataset.key = "place:" + place;
    if (place === S.current) a.setAttribute("aria-current", "page");
    inner.forEach(function (n) { a.appendChild(n); });
    counts(a, unread, important, muted);
    li.appendChild(a);
    if (place.charAt(0) === "#") {
      var gear = make("a", "place-gear"), label = t("chan.gear", {place: place});
      gear.href = settingsHref(place.slice(1));
      gear.setAttribute("aria-label", label);
      gear.title = label;
      gear.dataset.key = "gear:" + place;
      gear.appendChild(A.glyph("sliders"));
      li.appendChild(gear);
    }
    return li;
  }

  // A small lock after a channel's name: some members may not read it (a shape, not a colour; the words for readers).
  function lockMark() {
    var s = make("span", "lock-mark");
    s.title = t("nav.restricted");
    s.append(A.glyph("lock"), make("span", "vh", t("nav.restricted")));
    return s;
  }

  function privateItem(name, unread, important) {
    var who = S.directory[name], inner = [presence(who), make("span", "place-name", name)];
    if (who && who.kind === "agent" && who.owner === ME) inner.push(make("span", "note", t("nav.my_agent")));
    if (who && who.kind === "agent" && who.busy) inner.push(make("span", "note", t("nav.busy")));
    return item(name, inner, unread, important, false);
  }

  var drawn = "";
  function draw(force) {
    var p = S.places;
    if (!side) return;
    if (!p) {                                         // before the first answer: only the current mark
      Array.prototype.forEach.call(side.querySelectorAll("a.place[data-place]"), function (a) {
        if (a.dataset.place === S.current) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
      });
      return;
    }
    var key = JSON.stringify([p, S.current, S.directory]);
    if (key === drawn && !force) return;
    drawn = key;
    A.keepFocus(side, function () {
      if (lists.channels) {
        lists.channels.textContent = "";
        p.channels.forEach(function (c) {
          var inner = [make("span", "place-name", "#" + c.name)];
          if (c.restricted) inner.push(lockMark());
          if (c.muted) inner.push(make("span", "note", t("nav.muted")));
          lists.channels.appendChild(item("#" + c.name, inner, c.unread, c.important, c.muted));
        });
      }
      if (lists["private"]) {
        lists["private"].textContent = "";
        var seen = false;
        p["private"].forEach(function (c) {
          if (c["with"] === S.current) seen = true;
          lists["private"].appendChild(privateItem(c["with"], c.unread, c.important));
        });
        if (S.current && S.current.charAt(0) !== "#" && !seen) {     // a conversation not started yet
          lists["private"].insertBefore(privateItem(S.current, 0, 0), lists["private"].firstChild);
        }
        if (dmNone) dmNone.hidden = !!lists["private"].children.length;
      }
    });
  }

  // Several callers may ask at once; only the newest answer is drawn.
  var asked = 0;
  S.refresh = async function () {
    var mine = ++asked;
    var r = await A.request(API + "channels");
    if (!r.ok || mine !== asked) return S.places;
    S.places = {channels: r.data.channels || [], "private": r.data["private"] || []};
    draw(false);
    S.listeners.forEach(function (fn) { fn(S.places); });
    return S.places;
  };

  var membersRaw = "";
  S.loadMembers = async function () {
    var r = await A.request(API + "members");
    if (!r.ok) return S.members;
    var raw = JSON.stringify(r.data);
    if (raw === membersRaw) return S.members;
    membersRaw = raw;
    var d = {};
    (r.data.people || []).forEach(function (x) { d[x.name] = {kind: "person", online: !!x.online}; });
    (r.data.agents || []).forEach(function (a) { d[a.name] = {kind: "agent", online: !!a.online, owner: a.owner, busy: !!a.busy}; });
    S.directory = d;
    S.members = r.data;
    draw(false);
    S.memberListeners.forEach(function (fn) { fn(S.members); });
    return S.members;
  };

  setInterval(S.refresh, PLACES_EVERY_MS);
  setInterval(S.loadMembers, MEMBERS_EVERY_MS);
  S.refresh();

  // ------------------------------------------------------------------ presence: this page is open

  // A plain POST without an Idempotency-Key: a beat is the same however often it arrives, and nothing is kept of it.
  // It goes on while the page is hidden too (the person still has the project open).
  var BEAT_MS = Math.max(5, Number(rail.dataset.beat) || 20) * 1000;
  function beat() {
    return fetch(API + "presence", {method: "POST", credentials: "same-origin", body: "{}",
                                    headers: {"Content-Type": "application/json", "Accept": "application/json"}})
      .catch(function () { /* the next beat tries again */ });
  }
  // The first beat before the first reading of the members, so that the reader is online in it.
  beat().then(S.loadMembers);
  setInterval(beat, BEAT_MS);

  // ------------------------------------------------------------------ starting a private conversation

  function go(place) {
    if (A.rail) A.rail.closeDrawer(false);
    window.location.href = hrefOf(place);
  }

  // #dm-new: the members one may write to privately (two people; a person and their own agent), as a menu.
  var dmNew = document.getElementById("dm-new");
  if (dmNew) {
    dmNew.addEventListener("click", function () {
      var choices = A.parseJSON(dmNew.dataset.choices, []) || [];
      A.menu({label: t("nav.start_private"), anchor: dmNew}, choices.map(function (c) {
        return {label: c.agent ? t("msg.my_agent", {name: c.name}) : c.name, run: function () { go(c.name); }};
      }), dmNew);
    });
  }

  // ------------------------------------------------------------------ a channel's menu
  //
  // The outcome of an act (copied, a refusal) is said on the row for a moment (DESIGN: interaction).

  function channelOf(a) {
    var p = S.places && S.places.channels.filter(function (c) { return "#" + c.name === a.dataset.place; })[0];
    return p || null;
  }

  function sayOnRow(place, text) {
    var a = side.querySelector('a.place[data-place="' + place.replace(/["\\]/g, "\\$&") + '"]');
    if (!a) return;
    var note = make("span", "note row-said", text);
    note.setAttribute("role", "status");
    a.appendChild(note);
    setTimeout(function () { note.remove(); }, 2500);
  }

  async function markRead(name) {
    var r = await A.request(API + "messages", {"in": "#" + name, limit: 1});
    if (!r.ok) { sayOnRow("#" + name, A.refusal("chan.read", r.data)); return; }
    var msgs = r.data.messages || [], last = msgs.length ? msgs[msgs.length - 1].id : 0;
    if (last) {
      var done = await A.request(API + "read", null, {"in": "#" + name, upto: last});
      if (!done.ok) { sayOnRow("#" + name, A.refusal("chan.read", done.data)); return; }
    }
    await S.refresh();
  }

  async function mute(name, muted) {
    var r = await A.request(API + "channels/" + encodeURIComponent(name) + "/mute", null, {muted: muted});
    if (!r.ok) { sayOnRow("#" + name, A.refusal("chan.mute", r.data)); return; }
    await S.refresh();
  }

  function channelMenu(a, where) {
    var c = channelOf(a);
    if (!c) return;
    var name = c.name, place = "#" + name;
    var items = [
      {label: t("chan.mark_read"), disabled: !c.unread, run: function () { markRead(name); }},
      {label: t(c.muted ? "chan.unmute" : "chan.mute"), run: function () { mute(name, !c.muted); }},
      {label: t("chan.copy"), run: async function () {
        var ok = await A.copy(window.location.origin + hrefOf(place));
        sayOnRow(place, t(ok ? "chan.copied" : "chan.copy_failed"));
      }},
      {label: t("chan.settings"), href: settingsHref(name)}];
    if (A.can("create_channel") && A.project) {
      items.push({separator: true}, {label: t("chan.new"), run: function () { A.project.act("new-channel", a); }});
    }
    A.menu(Object.assign({label: t("chan.acts", {place: place})}, where), items, a);
  }

  if (side && lists.channels) {
    lists.channels.addEventListener("contextmenu", function (ev) {
      var a = ev.target.closest && ev.target.closest("a.place[data-place]");
      if (!a) return;
      ev.preventDefault();
      channelMenu(a, {x: ev.clientX, y: ev.clientY});
    });
    lists.channels.addEventListener("keydown", function (ev) {
      var a = ev.target.closest && ev.target.closest("a.place[data-place]");
      if (!a || !(ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey))) return;
      ev.preventDefault();
      channelMenu(a, {anchor: a});
    });
  }
})();
