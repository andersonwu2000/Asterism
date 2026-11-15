// The places of a project on every page of it (Asterism.side): /api/channels on the pages' rhythm (the rail counts
// what is important from it; the messages page reads the places), the presence marks from /api/members, and in chat
// the second column (#side) with its channels (#side-channels) and private conversations (#side-private), and the
// forms to create a channel and to start a private conversation. The rail and the drawer are rail.js's.
"use strict";
(function () {
  var A = window.Asterism, rail = document.getElementById("rail"), side = document.getElementById("side");
  if (!A || !rail) return;
  var t = A.t, make = A.make;
  var SLUG = rail.dataset.slug, ME = rail.dataset.me;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var PLACES_EVERY_MS = 4000, MEMBERS_EVERY_MS = 15000;
  var lists = {channels: document.getElementById("side-channels"), "private": document.getElementById("side-private")};

  var S = A.side = {
    places: null,                     // what /api/channels answered last
    directory: A.parseJSON(rail.dataset.directory, {}),   // name -> {kind, online, owner}
    current: null,                    // the place open on the messages page
    listeners: []
  };
  S.onChange = function (fn) { S.listeners.push(fn); if (S.places) fn(S.places); };
  S.setCurrent = function (place) { S.current = place; draw(true); };

  // ------------------------------------------------------------------ the lists

  function hashOf(place) { return "#" + encodeURIComponent(place); }
  function hrefOf(place) { return "/" + encodeURIComponent(SLUG) + hashOf(place); }

  function presence(who) {
    var mark = make("span", "presence");
    mark.setAttribute("role", "img");
    if (who && who.kind === "agent") {
      mark.className += " agent" + (who.online ? " on" : "");
      mark.setAttribute("aria-label", t(who.online ? "presence.online" : "presence.offline"));
    } else {
      mark.className += " person";
      mark.setAttribute("aria-label", t("presence.person"));
    }
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

  function item(place, inner, unread, important, muted) {
    var li = make("li"), a = make("a", "place" + (unread && !muted ? " unread" : "") + (muted ? " muted" : ""));
    a.href = hrefOf(place);
    a.dataset.place = place;
    a.dataset.key = "place:" + place;
    if (place === S.current) a.setAttribute("aria-current", "page");
    inner.forEach(function (n) { a.appendChild(n); });
    counts(a, unread, important, muted);
    li.appendChild(a);
    return li;
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
      lists.channels.textContent = "";
      p.channels.forEach(function (c) {
        var inner = [make("span", "place-name", "#" + c.name)];
        if (c.muted) inner.push(make("span", "note", t("nav.muted")));
        lists.channels.appendChild(item("#" + c.name, inner, c.unread, c.important, c.muted));
      });
      lists["private"].textContent = "";
      var seen = false;
      p["private"].forEach(function (c) {
        if (c["with"] === S.current) seen = true;
        lists["private"].appendChild(privateItem(c["with"], c.unread, c.important));
      });
      if (S.current && S.current.charAt(0) !== "#" && !seen) {     // a conversation not started yet
        lists["private"].insertBefore(privateItem(S.current, 0, 0), lists["private"].firstChild);
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

  async function loadMembers() {
    var r = await A.request(API + "members");
    if (!r.ok) return;
    var d = {};
    (r.data.people || []).forEach(function (x) { d[x.name] = {kind: "person"}; });
    (r.data.agents || []).forEach(function (a) { d[a.name] = {kind: "agent", online: !!a.online, owner: a.owner, busy: !!a.busy}; });
    S.directory = d;
    draw(false);
  }

  setInterval(S.refresh, PLACES_EVERY_MS);
  setInterval(loadMembers, MEMBERS_EVERY_MS);
  S.refresh();

  // ------------------------------------------------------------------ creating a channel, starting a conversation

  function reveal(button, show) {
    var form = document.getElementById(button.getAttribute("aria-controls"));
    if (!form) return;
    form.hidden = !show;
    button.setAttribute("aria-expanded", String(show));
    if (show) {
      var field = form.querySelector("input, select");
      if (field) field.focus();
    } else {
      button.focus();
    }
  }
  Array.prototype.forEach.call(side ? side.querySelectorAll("[data-reveal]") : [], function (b) {
    var form = document.getElementById(b.getAttribute("aria-controls"));
    b.addEventListener("click", function () { reveal(b, form.hidden); });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.stopPropagation(); reveal(b, false); }
    });
    var cancel = form.querySelector("[data-dismiss]");
    if (cancel) cancel.addEventListener("click", function () { reveal(b, false); });
  });

  function go(place) {
    if (A.rail) A.rail.closeDrawer(false);
    window.location.href = hrefOf(place);
  }

  var newChannel = document.getElementById("new-channel");
  if (newChannel) {
    newChannel.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var input = newChannel.elements.name, out = newChannel.querySelector("[data-out]");
      var r = await A.request(API + "channels", null, {name: input.value.trim().replace(/^#/, "")});
      if (!r.ok) { out.textContent = A.errorText(r.data.error); return; }
      out.textContent = "";
      input.value = "";
      newChannel.hidden = true;
      side.querySelector('[aria-controls="new-channel"]').setAttribute("aria-expanded", "false");
      await S.refresh();
      go("#" + r.data.name);
    });
  }
  var newPrivate = document.getElementById("new-private");
  if (newPrivate) {
    newPrivate.addEventListener("submit", function (ev) {
      ev.preventDefault();
      newPrivate.hidden = true;
      side.querySelector('[aria-controls="new-private"]').setAttribute("aria-expanded", "false");
      go(newPrivate.elements["with"].value);
    });
  }

})();
